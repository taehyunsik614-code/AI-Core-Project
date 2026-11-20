import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from day3 import context, decide

class Rules(unittest.TestCase):
    def ask(self,text,mode='direction',tool='move',local=False,**extras):
        ctx,_=context({'text':text,**extras},mode)
        return decide(ctx,{'tool':tool,'direction':'right','steps':1,'guess':'right'},local)
    def test_direction_chain(self):
        r=self.ask('오른쪽 2칸 가고 위로 1칸')
        self.assertEqual((r['args'],r['then']),({'direction':'right','steps':2},{'direction':'up','steps':1}))
        self.assertNotIn('칸',r['message'])
        self.assertIn('2칸',self.ask('오른쪽 두 칸',local=True)['message'])
    def test_uncertain_confirm_and_correct(self):
        p=self.ask('저쪽으로 2칸')['pending']
        for answer,d in [('응','right'),('왼쪽','left')]:
            self.assertEqual(self.ask(answer,pending=p)['args'],{'direction':d,'steps':2})
    def test_kitchen(self):
        p=self.ask('두 단계 이동해 줘','kitchen')['pending']
        self.assertEqual(self.ask('다음으로','kitchen',pending=p)['args'],{'direction':'next','steps':2})
        self.assertEqual(self.ask('얼마나 기다려?','kitchen','describe')['args']['topic'],'time')
    def test_range_invalid_output_and_gesture(self):
        self.assertEqual(self.ask('오른쪽 99칸')['args']['steps'],10)
        self.assertEqual(self.ask('이동',gesture_direction='up')['args']['direction'],'up')
        self.assertEqual(decide({'text':'안녕','mode':'direction'},None)['tool'],'describe')

    def test_device_reply_then_confirmation_across_input_sources(self):
        import json
        from unittest.mock import patch
        from day3_api import Diagnostics
        packets=[]
        def relay(ip,path,payload,timeout):
            self.assertEqual((ip,path),('127.0.0.1','/llm-infer'))
            packets.append(payload)
            return json.dumps({'tool':'move','args':{'direction':'right','steps':2}}).encode()
        api=Diagnostics('127.0.0.1',None)
        with patch('day3_api.device.relay',relay):
            r=api.answer({'source':'voice','prompt':'저쪽 두 칸'},'direction')
            self.assertTrue(r['need_more_info'])
            history=[{'role':'user','content':'저쪽 두 칸'},{'role':'assistant','content':r['message']}]
            follow=api.answer({'source':'device','prompt':'응','history':history},'direction')
            self.assertEqual(follow['args'],{'direction':'right','steps':2})
            self.assertEqual(packets[-1]['mode'],'direction')
