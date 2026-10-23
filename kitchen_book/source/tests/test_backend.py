import base64
import io
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
import config
import schema
from ai import decode_image, KitchenAI
from app import Jobs, create_app
from fastapi.testclient import TestClient

_DETECTOR_PATCH = patch.object(config, 'DETECTOR', 'vlm')
def setUpModule(): _DETECTOR_PATCH.start()
def tearDownModule(): _DETECTOR_PATCH.stop()

class SchemaTests(unittest.TestCase):
    def test_fenced_and_thinking_json(self):
        data = schema.parse_json('<think>analysis</think>\n```json\n{"ingredients":["달걀"],"uncertain":[]}\n```')
        self.assertEqual(schema.ingredients(data)['ingredients'], ['달걀'])

    def test_reject_truncated_json(self):
        with self.assertRaises(schema.OutputError):
            schema.parse_json('{"steps":[')

    def test_reject_hallucinated_timer_format(self):
        for invalid in [True, -1, 86401, 'three minutes', 1.5]:
            with self.subTest(value=invalid), self.assertRaises(schema.OutputError):
                schema.recipe({'title':'요리', 'ingredients':['달걀 1개'], 'steps':[{'title':'익히기','instruction':'익힌다','timer_seconds':invalid}]})

    def test_reject_empty_menu_or_ingredients(self):
        with self.assertRaises(schema.OutputError):
            schema.menus({'menus':[]})
        with self.assertRaises(schema.OutputError):
            schema.strings([], '재료', 1)

    def test_decode_reject_nonimage(self):
        with self.assertRaises(ValueError):
            decode_image('data:image/jpeg;base64,'+base64.b64encode(b'not a photo').decode())

class TimerRecoveryTests(unittest.TestCase):
    def book(self, instruction, **values):
        return schema.recipe({'title':'요리', 'ingredients':['재료'], 'steps':[{'title':'조리','instruction':instruction,**values}]})['steps'][0]

    def test_missing_zero_and_conflicting_timer_are_recovered(self):
        for values in [{}, {'timer_seconds':0}, {'timer_seconds':60}, {'timer_seconds':'180'}]:
            with self.subTest(values=values):
                self.assertEqual(self.book('3분간 볶습니다.', **values)['timer_seconds'],180)

    def test_no_time_is_not_invented(self):
        self.assertEqual(self.book('재료를 섞습니다.')['timer_seconds'],0)
        self.assertEqual(self.book('익힌 뒤 마무리합니다.',timer_seconds=120)['timer_seconds'],120)

    def test_duration_corpus(self):
        from durations import duration_from_text
        cases=json.loads((Path(__file__).parent/'duration_cases.json').read_text())
        for text,expected in cases:
            with self.subTest(text=text):
                self.assertEqual(duration_from_text(text),expected)

    def test_verification_rejects_added_or_missing_candidates(self):
        for checks in [[],[{'name':'다른재료','visible':True,'evidence':'보임'}],[{'name':'후보','visible':'yes','evidence':'보임'}]]:
            with self.assertRaises(schema.OutputError):
                schema.verification({'checks':checks},['후보'])

class VisionFormatTests(unittest.TestCase):
    def test_root_array_keeps_all_candidates(self):
        data=schema.parse_json('[{"name":"양파","evidence":"둥근 표면"},{"name":"파프리카","evidence":"굴곡진 표면"}]',allow_array=True)
        self.assertEqual([o['name'] for o in schema.observations(data)['objects']],['양파','파프리카'])

    def test_legacy_list_names_are_not_given_invented_visual_evidence(self):
        for data in [{'ingredients':['양파','버섯']}, ['양파','버섯'], {'재료':['양파','버섯']}]:
            result=schema.observations(data)
            self.assertEqual([o['name'] for o in result['objects']],['양파','버섯'])
            self.assertIn('특징이 없는 후보',result['objects'][0]['evidence'])

    def test_single_object_is_wrapped(self):
        self.assertEqual(schema.observations({'objects':{'name':'양파','evidence':'둥근 표면'}})['objects'][0]['name'],'양파')

    def test_truncated_root_is_not_replaced_by_inner_object(self):
        with self.assertRaises(schema.OutputError):
            schema.parse_json('[{"name":"양파","evidence":"둥근 표면"}',allow_array=True)

    def test_unknown_fields_do_not_mean_no_ingredients(self):
        with self.assertRaisesRegex(schema.OutputError,'description'):
            schema.observations({'description':'사진 설명'})

    def test_too_many_candidates_are_bounded_and_disclosed(self):
        result=schema.observations({'ingredients':[str(n) for n in range(14)]})
        self.assertEqual(len(result['objects']),12)
        self.assertTrue(result['uncertain'])

class AIAdapterTests(unittest.TestCase):
    @patch.object(config, 'AI_ATTEMPTS', 2)
    def test_invalid_generation_is_retried_then_validated(self):
        class FakeModel:
            def __init__(self):
                self.calls=[]
            def create_chat_completion(self, **kwargs):
                self.calls.append(kwargs)
                text='not JSON' if len(self.calls)==1 else '{"ingredients":["달걀"],"uncertain":[]}'
                return {'choices':[{'message':{'content':text}}]}
        ai=KitchenAI()
        model=FakeModel()
        ai._load=lambda kind:model
        result=ai._ask('vlm','재료 확인',schema.ingredients,Image.new('RGB',(20,20)))
        self.assertEqual(result['ingredients'],['달걀'])
        self.assertEqual(len(model.calls),2)
        content=model.calls[0]['messages'][1]['content']
        self.assertEqual(content[0]['type'],'image_url')
        self.assertTrue(content[0]['image_url']['url'].startswith('data:image/jpeg;base64,'))

    @patch.object(config, 'VERIFY_IMAGE', True)
    def test_same_photo_is_verified_and_rejected_candidate_is_removed(self):
        outputs=[{'objects':[{'name':'재료A','evidence':'둥근 표면'},{'name':'재료B','evidence':'잘 보이지 않음'}],'uncertain':[]},
                 {'checks':[{'name':'재료A','visible':True,'evidence':'특징 일치'},{'name':'재료B','visible':False,'evidence':'사진에서 확인 안 됨'}]}]
        class Fake:
            def __init__(self):self.calls=[]
            def create_chat_completion(self,**kwargs):
                self.calls.append(kwargs)
                return {'choices':[{'message':{'content':json.dumps(outputs[len(self.calls)-1],ensure_ascii=False)}}]}
        ai=KitchenAI();model=Fake();ai._load=lambda kind:model
        buffer=io.BytesIO();Image.new('RGB',(1000,750)).save(buffer,'JPEG')
        result=ai.run('ingredients',{'image':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()})
        self.assertEqual(result['ingredients'],['재료A'])
        self.assertIn('재료B',result['uncertain'][0])
        self.assertTrue(result['review_required'])
        self.assertEqual(result['image_info']['width'],448)
        images=[c['messages'][1]['content'][0]['image_url']['url'] for c in model.calls]
        self.assertEqual(images[0],images[1])
        self.assertTrue(all(c['temperature']==0 for c in model.calls))
        self.assertNotIn('토마토',model.calls[0]['messages'][1]['content'][1]['text'])
        self.assertEqual(model.calls[0]['response_format']['schema']['required'],['objects','uncertain'])
        self.assertEqual(model.calls[1]['response_format']['schema']['properties']['checks']['items']['properties']['name']['enum'],['재료A','재료B'])

    def test_empty_photo_does_not_invent_ingredients(self):
        ai=KitchenAI()
        calls=[]
        def ask(kind,prompt,validator,image=None,**kwargs):
            calls.append(prompt)
            return validator({'objects':[],'uncertain':['재료 없음']})
        ai._ask=ask
        buffer=io.BytesIO();Image.new('RGB',(20,20)).save(buffer,'JPEG')
        result=ai.run('ingredients',{'image':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()})
        self.assertEqual(result['ingredients'],[])
        self.assertEqual(len(calls),1)

    @patch.object(config, 'VERIFY_IMAGE', True)
    def test_failed_second_pass_keeps_explicitly_unverified_candidates(self):
        ai=KitchenAI();calls=[]
        def ask(kind,prompt,validator,image=None,**kwargs):
            calls.append(kwargs)
            if len(calls)==1:
                return validator({'objects':[{'name':'양파','evidence':'둥근 표면'}],'uncertain':[]})
            raise schema.OutputError('재확인 형식 오류')
        ai._ask=ask
        buffer=io.BytesIO();Image.new('RGB',(20,20)).save(buffer,'JPEG')
        result=ai.run('ingredients',{'image':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()})
        self.assertEqual(result['ingredients'],['양파'])
        self.assertEqual(result['verification_status'],'unverified')
        self.assertTrue(result['review_required'])
        self.assertIn('미검증',result['uncertain'][0])
        self.assertTrue(all('response_schema' in c for c in calls))

    def test_model_failure_never_falls_back_to_demo(self):
        ai=KitchenAI()
        def unavailable(kind):
            raise FileNotFoundError('model missing')
        ai._load=unavailable
        with self.assertRaises(FileNotFoundError):
            ai.run('menus',{'ingredients':['달걀']})

class JobTests(unittest.TestCase):
    def test_jobs_cannot_overlap_and_errors_recover(self):
        started, resume = threading.Event(), threading.Event()
        class Fake:
            def run(self,kind,payload):
                started.set()
                resume.wait(3)
                raise ValueError('모델 오류')
        jobs = Jobs(Fake())
        job_id=jobs.submit('menus', {})
        self.assertTrue(started.wait(1))
        with self.assertRaises(BlockingIOError):
            jobs.submit('menus', {})
        resume.set()
        for _ in range(100):
            if jobs.get(job_id)['status']!='running':break
            time.sleep(.01)
        self.assertEqual(jobs.get(job_id)['status'], 'error')
        self.assertIsNone(jobs.active)
        jobs.pool.shutdown()

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(create_app(demo=True))
        cls.client.__enter__()
        cls.csrf=cls.call('/api/health')['csrf']

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)

    @classmethod
    def call(cls,path,payload=None,csrf=True):
        headers={'X-Kitchen-Token':cls.csrf} if payload is not None and csrf else {}
        response=cls.client.get(path) if payload is None else cls.client.post(path,json=payload,headers=headers)
        if response.status_code>=400: raise HTTPError(path,response.status_code,response.text,{},None)
        return response.json()

    def job(self,path,payload):
        job_id=self.call(path,payload)['job_id']
        for _ in range(100):
            job=self.call('/api/jobs/'+job_id)
            if job['status']!='running':break
            time.sleep(.01)
        self.assertEqual(job['status'],'done',job)
        return job['result']

    def test_full_demo_workflow(self):
        buffer=io.BytesIO();Image.new('RGB',(80,60)).save(buffer,'JPEG')
        image='data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()
        items=self.job('/api/ingredients',{'image':image})['ingredients']
        menus=self.job('/api/menus',{'ingredients':items})['menus']
        self.assertEqual(len(menus),3)
        book=self.job('/api/recipe',{'ingredients':items,'menu':menus[0]})
        self.assertGreater(len(schema.recipe(book)['steps']),1)
        self.assertGreater(book['steps'][1]['timer_seconds'],0)

    def test_bad_requests_and_unknown_job(self):
        for path,payload,csrf,expected in [('/api/menus',{'ingredients':[]},True,400),('/api/recipe',{'ingredients':['달걀']},True,400),('/api/menus',{'ingredients':['달걀']},False,403),('/api/jobs/missing',None,True,404)]:
            with self.subTest(path=path,expected=expected),self.assertRaises(HTTPError) as result:
                self.call(path,payload,csrf)
            self.assertEqual(result.exception.code,expected)

if __name__=='__main__':
    unittest.main()
