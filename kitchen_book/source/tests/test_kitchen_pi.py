import base64
import io
import json
import sys
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'source'), str(ROOT/'raspberrypi')]
import camera_server
import device
from ai import KitchenAI
from gestures import landmark_pose
from types import SimpleNamespace

class KitchenDeviceTest(unittest.TestCase):
    def test_independent_views_keep_shared_names_and_flag_disagreement(self):
        ai = KitchenAI()
        observed = iter([['감자','당근'],['감자'],['양파']])
        sizes = []
        def answer(kind, prompt, validator, image, **options):
            if 'checks' in options['response_schema']['properties']:
                return validator({'checks':[dict(name=n,visible=n=='양파',evidence='형태 확인') for n in ['당근','양파']]})
            sizes.append(image.size)
            return validator({'objects':[{'name':n,'evidence':'표면 특징'} for n in next(observed)]})
        ai._ask = answer
        result = ai.scan(Image.new('RGB',(1280,720)), 'multi')
        self.assertEqual(result['ingredients'], ['감자','양파'])
        self.assertIn('당근', result['uncertain'][0])
        self.assertNotEqual(sizes[0], sizes[1])

    def test_disjoint_views_prefill_review_and_skip_placeholder(self):
        ai = KitchenAI()
        ai._ask = Mock(side_effect=[{'objects':[dict(name=n,evidence='특징') for n in names],'uncertain':[]}
                                    for names in (['이름','양파'],['고추'],[])] + [[dict(name=n,visible=True,evidence='형태 확인') for n in ['양파','고추']]])
        result = ai.scan(Image.new('RGB',(100,80)), 'multi')
        self.assertEqual(result['ingredients'], ['양파','고추'])
        self.assertTrue(result['review_required'])

    def test_localizes_names_and_evidence_before_display(self):
        ai = KitchenAI()
        def answer(kind,prompt,validator,image=None,**kw):
            if kind == 'llm':
                return validator({'0':'리가토니','1':'속이 빈 원통형 면'})
            return validator({'objects':[dict(name='rigatoni',evidence='hollow pasta')],'uncertain':[]})
        ai._ask=answer
        result=ai.scan(Image.new('RGB',(64,64)), 'single')
        self.assertEqual(result['ingredients'], ['리가토니'])
        self.assertEqual(result['evidence'][0]['evidence'], '속이 빈 원통형 면')

    def test_carrot_and_uncertain(self):
        ai=KitchenAI()
        ai._ask=Mock(return_value={'objects':[dict(name=n,evidence='길쭉한 형태') for n in ['carrot','uncertain']], 'uncertain':[]})
        self.assertEqual(ai.scan(Image.new('RGB',(64,64)), 'multi')['ingredients'], ['당근'])

    def test_quick_scan_uses_one_image(self):
        ai=KitchenAI()
        ai._ask=Mock(return_value=['carrot','양파','uncertain'])
        result=ai.scan(Image.new('RGB',(1280,720)), 'quick')
        self.assertEqual(result['ingredients'], ['당근','양파'])
        self.assertEqual(ai._ask.call_count, 1)
        self.assertEqual(ai._ask.call_args.args[3].width,672)

    def test_short_recipe_and_repeated_request(self):
        ai=KitchenAI()
        data=dict(ingredients=['감자 한 개'],steps=[dict(title='준비',instruction='감자를 씻는다.'),
                  dict(title='가열',instruction='3분 끓인다.'),dict(title='완성',instruction='그릇에 담는다.')])
        ai._ask=Mock(side_effect=lambda k,p,v,**kw:v(data))
        payload=dict(menu=dict(name='감자국',missing=[]),ingredients=['감자'])
        book=ai.run('recipe',payload)
        self.assertEqual(book['steps'][1]['timer_seconds'],180)
        self.assertEqual(ai.run('recipe',payload),book)
        self.assertEqual(ai._ask.call_count,1)

    def test_finger_patterns(self):
        def hand(opens):
            points=[SimpleNamespace(x=0,y=0,z=0) for _ in range(21)]
            for i,base in enumerate((5,9,13,17)):
                ys=(1,1.5,2,2.5) if opens[i] else (1,1.5,1.2,.9)
                for offset,y in enumerate(ys):
                    points[base+offset]=SimpleNamespace(x=i*.25,y=y,z=0)
            return points
        self.assertEqual(landmark_pose(hand([1,0,0,0])), 'Pointing_Up')
        self.assertEqual(landmark_pose(hand([1,1,1,1])), 'Open_Palm')
        self.assertIsNone(landmark_pose(hand([1,1,0,0])))
        self.assertIsNone(landmark_pose(hand([0,0,0,0])))

    def test_ambiguous_closeup(self):
        ai = KitchenAI()
        ai._ask = Mock(return_value={'objects':[dict(name=n,evidence='특징') for n in ['감자','당근']],'uncertain':[]})
        self.assertFalse(ai.scan(Image.new('RGB',(64,64)), 'single')['ingredients'])

    def test_pi_http_outputs_and_frame_relay(self):
        # Real loopback HTTP, fake camera frame, display and LEDs.
        oled, running, done, screen = Mock(), Mock(), Mock(), Mock()
        @contextmanager
        def draw(display):
            yield screen
        outputs = camera_server.Outputs(oled,running,done,draw)
        frames = camera_server.Frames(None)
        buf = io.BytesIO()
        Image.new('RGB',(32,24)).save(buf,'JPEG')
        frames.latest, frames.timestamp = buf.getvalue(), time.monotonic()
        server = ThreadingHTTPServer(('127.0.0.1',0),camera_server.handler(frames,outputs))
        from http.client import HTTPConnection
        def connect(ip,port,timeout):
            return HTTPConnection(ip,server.server_port,timeout=timeout)
        worker = threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            with patch('device.http.client.HTTPConnection',side_effect=connect):
                self.assertEqual(device.relay('127.0.0.1','/frame.jpg'),buf.getvalue())
                for mode in ['step','running','finished','finished']:
                    v = device.state(dict(page=2,total=5,seconds=120,mode=mode))
                    self.assertTrue(json.loads(device.relay('127.0.0.1','/state',v))['ok'])
                    self.assertEqual(running.value,mode=='running')
                v=device.state(dict(page=2,total=5,mode='step',seconds=0,bitmap=base64.b64encode(bytes(1024)).decode()))
                self.assertTrue(json.loads(device.relay('127.0.0.1','/state',v))['ok'])
                self.assertEqual(screen.bitmap.call_args.args[1].size,(128,64))
                for stage in (1,2,3,4):
                    v = device.state(dict(stage=stage,page=1 if stage==4 else 0,total=4 if stage==4 else 0,
                                          seconds=0,mode='step' if stage==4 else 'idle'))
                    ack=json.loads(device.relay('127.0.0.1','/state',v))
                    self.assertEqual((ack['stage'],ack['page']),(stage,v['page']))
                    self.assertEqual(screen.bitmap.call_args.args[1].size,(128,18))
                self.assertIn('1/4',str(screen.text.call_args_list))
                done.blink.assert_called_once_with(on_time=.3,off_time=.3,n=3,background=True)
                self.assertIn('STEP 2/5',str(screen.text.call_args_list))
                self.assertIn('TIMER 02:00',str(screen.text.call_args_list))
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
