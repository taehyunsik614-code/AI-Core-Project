import sys, json, unittest, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import parse_tool_call, apply_rules, validate_request, answer, call, gesture_evidence
from ai import KitchenAI

CONTEXT={'page':1,'total_pages':5,'timer_seconds':180,'step_seconds':120}
def resolve(text, history=None, gesture=None, raw=None, **context):
    payload=validate_request({'prompt':text,'context':{**CONTEXT,**context},'history':history or [],'gesture':gesture or {}})
    return apply_rules(parse_tool_call(raw or {'tool':'ask','args':{},'message':''}),payload)

def pending(text,result):
    return [{'role':'user','content':text},{'role':'assistant',**result}]

class RulesTests(unittest.TestCase):
    def test_R1_unknown_and_malformed(self):
        for raw in ['{','[]','{"tool":"delete"}',{'tool':'timer','args':[]}]:
            with self.subTest(raw=raw): self.assertIn(parse_tool_call(raw)['tool'],('ask','describe'))
    def test_R2_arguments(self):
        self.assertEqual(parse_tool_call({'tool':'page','args':{'direction':'다음','steps':999}})['args'],{'direction':'next','steps':10})
        self.assertEqual(parse_tool_call({'tool':'page','args':{'steps':3}})['tool'],'ask')
        self.assertEqual(parse_tool_call({'tool':'timer','args':{'action':'set','seconds':True}})['tool'],'ask')
    def test_R3_hallucinations_blocked(self):
        for prompt in ['저쪽으로 해줘','버스 위치로 가','요리 제목','다음에 요리하자']:
            self.assertNotIn(resolve(prompt,raw={'tool':'page','args':{'direction':'next','steps':2}})['tool'],('page','timer'))
        result=resolve('타이머 설정',raw={'tool':'timer','args':{'action':'set','seconds':900}})
        self.assertEqual(result['tool'],'ask')
    def test_R4_flag(self):
        for text in ['다음 페이지','타이머','타이머 2분 설정','설명해 줘']:
            result=resolve(text);self.assertEqual(result['need_more_info'],result['tool']=='ask')
    def test_R5_page_followup(self):
        first=resolve('2페이지 넘겨');self.assertEqual(first['tool'],'ask')
        second=resolve('이전',pending('2페이지 넘겨',first));self.assertEqual(second['args'],{'direction':'previous','steps':2})
    def test_R5_timer_followup(self):
        first=resolve('타이머 설정');second=resolve('3분',pending('타이머 설정',first))
        self.assertEqual(second['args'],{'action':'set','seconds':180})
        first=resolve('타이머 3분');second=resolve('설정',pending('타이머 3분',first))
        self.assertEqual(second['args'],{'action':'set','seconds':180})
    def test_start_without_time_followup(self):
        first=resolve('타이머 시작',timer_seconds=0)
        second=resolve('3분',pending('타이머 시작',first),timer_seconds=0)
        self.assertEqual(second['args'],{'action':'set','seconds':180})
    def test_old_history_is_not_evidence(self):
        history=[{'role':'user','content':'다음 2페이지'},{'role':'assistant','tool':'page','args':{'direction':'next','steps':2}}]
        self.assertEqual(resolve('페이지 넘겨',history)['tool'],'ask')
    def test_F306_priority_and_age(self):
        hand={'name':'Thumb_Down','mode':'book','stable':True,'score':.99,'age_ms':100}
        self.assertEqual(resolve('다음 2페이지',gesture=hand)['args']['direction'],'next')
        self.assertEqual(resolve('이쪽으로 2페이지',gesture=hand)['args']['direction'],'previous')
        for change in [{'age_ms':1500},{'score':.2},{'stable':False},{'name':'None'}]:
            self.assertEqual(resolve('이쪽으로 2페이지',gesture={**hand,**change})['tool'],'ask')
    def test_pending_priority_over_gesture(self):
        hand={'name':'Thumb_Down','mode':'timer','stable':True,'score':.99,'age_ms':0}
        first=resolve('타이머 설정')
        self.assertEqual(resolve('2분',pending('타이머 설정',first),hand)['args']['action'],'set')
    def test_mirror_invariant(self):
        hand={'name':'Thumb_Up','mode':'book','stable':True,'score':.99,'age_ms':0}
        self.assertEqual(resolve('이쪽 2페이지',gesture=hand),resolve('이쪽 2페이지',gesture={**hand,'mirrored':True}))
    def test_negative_and_multiple_intents(self):
        self.assertEqual(resolve('다음 말고 이전 페이지')['args']['direction'],'previous')
        for text in ['다음 말고 넘겨','다음 이전 페이지','다음 페이지 그리고 타이머 시작','타이머 시작하지 마']:
            self.assertNotIn(resolve(text)['tool'],('page','timer'))
    def test_explicit_actions_and_limits(self):
        for text,args in [('타이머 3분 설정',{'action':'set','seconds':180}),('타이머 30초 줄여',{'action':'adjust','seconds':-30}),('타이머 두 분 설정',{'action':'set','seconds':120}),('이 단계 시간 설정',{'action':'set','seconds':120}),('타이머 일시정지',{'action':'pause'}),('타이머 초기화',{'action':'reset'}),('타이머 999999초 설정',{'action':'set','seconds':86400})]:
            with self.subTest(text=text):self.assertEqual(resolve(text)['args'],args)
    def test_book_required(self):
        self.assertEqual(resolve('다음 페이지',total_pages=0)['tool'],'ask')
    def test_request_validation(self):
        for payload in [{'prompt':''},{'prompt':'x','history':'x'},{'prompt':'x','context':{'page':99}},{'prompt':'x','gesture':[]}]:
            with self.assertRaises(ValueError):validate_request(payload)
    def test_real_adapter_calls_llm_schema(self):
        ai=KitchenAI();calls=[]
        def fake(kind,prompt,validator,**kwargs):
            calls.append(kwargs);return validator({'tool':'page','args':{'direction':'next','steps':1},'message':'다음'})
        ai._ask=fake
        result=ai.run('intent',{'prompt':'다음 페이지','context':CONTEXT})
        self.assertEqual(result['inference_mode'],'qwen');self.assertEqual(result['tool'],'page')
        self.assertEqual(calls[0]['response_schema']['properties']['tool']['enum'],['page','timer','describe','ask'])
    def test_demo_disclosed(self):
        result=KitchenAI(True).run('intent',{'prompt':'다음 페이지','context':CONTEXT})
        self.assertEqual(result['inference_mode'],'demo_rules')

class DetectionTests(unittest.TestCase):
    def test_no_class_index_guess(self):
        from detection import IngredientDetector
        from PIL import Image
        from types import SimpleNamespace
        class Tensor:
            def __init__(self,x):self.x=x
            def cpu(self):return self
            def tolist(self):return self.x
        model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(names={5:'Tomato',11:'UnknownFood'},boxes=SimpleNamespace(xyxy=Tensor([[1,2,30,40],[10,20,30,40]]),conf=Tensor([.9,.3]),cls=Tensor([5,11])))])
        with tempfile.NamedTemporaryFile() as f,patch('config.model_path',return_value=Path(f.name)):
            d=IngredientDetector();d.model=model;d.aliases={'Tomato':'토마토'};p=Path(f.name);d.signature=(str(p),p.stat().st_mtime_ns,p.stat().st_size)
            result=d.detect(Image.new('RGB',(100,100)))
        self.assertEqual(result['ingredients'],['토마토']);self.assertIn('UnknownFood',result['uncertain'][0]);self.assertEqual(result['objects'][0]['class_id'],5)
    def test_wrong_class_count_is_rejected(self):
        from detection import IngredientDetector
        from PIL import Image
        from types import SimpleNamespace
        with tempfile.NamedTemporaryFile() as f,patch('config.model_path',return_value=Path(f.name)),patch.dict(sys.modules,{'ultralytics':SimpleNamespace(YOLO=lambda *a,**k:SimpleNamespace(names={0:'person'}))}):
            with self.assertRaisesRegex(ValueError,'120'):IngredientDetector().detect(Image.new('RGB',(10,10)))

if __name__=='__main__':unittest.main()
