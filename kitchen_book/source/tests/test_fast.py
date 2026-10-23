import base64
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from ai import KitchenAI
import config
import schema
import output_formats

_DETECTOR_PATCH = patch.object(config, 'DETECTOR', 'vlm')
def setUpModule(): _DETECTOR_PATCH.start()
def tearDownModule(): _DETECTOR_PATCH.stop()

class FastTests(unittest.TestCase):
    def test_single_pass_and_cache(self):
        ai=KitchenAI();calls=[]
        def ask(kind,prompt,validator,image=None,**kwargs):
            calls.append(image.size)
            return validator({'objects':[{'name':'달걀','evidence':'타원형'}],'uncertain':[]})
        ai._ask=ask
        buf=io.BytesIO();Image.new('RGB',(1280,720)).save(buf,'JPEG')
        payload={'image':'data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()}
        with patch.object(config,'VERIFY_IMAGE',False):
            first=ai.run('ingredients',payload)
            self.assertEqual(first['verification_status'],'single_pass')
            first['ingredients'].append('변조')
            second=ai.run('ingredients',payload)
        self.assertEqual(second['ingredients'],['달걀'])
        self.assertEqual(calls,[(448,252)])

    def test_cache_request_and_menu_isolation_and_bound(self):
        ai=KitchenAI();calls=[]
        ai._run=lambda kind,payload: calls.append((kind,payload)) or {'value':len(calls)}
        a={'ingredients':['달걀'],'request':'1인분'}
        self.assertEqual(ai.run('menus',a),ai.run('menus',dict(reversed(list(a.items())))))
        ai.run('menus',{**a,'request':'2인분'})
        ai.run('recipe',{**a,'menu':{'name':'계란말이'}})
        ai.run('recipe',{**a,'menu':{'name':'달걀찜'}})
        self.assertEqual(len(calls),4)
        for n in range(30):ai.run('menus',{'ingredients':[str(n)]})
        self.assertEqual(len(ai.cache),24)

    def test_text_generation_constrained(self):
        ai=KitchenAI();calls=[]
        def ask(kind,prompt,validator,**kwargs):calls.append(kwargs);return {}
        ai._ask=ask
        ai.run('menus',{'ingredients':['달걀']})
        ai.run('recipe',{'ingredients':['달걀'],'menu':{'name':'계란말이'}})
        self.assertEqual(calls[0]['response_schema'],output_formats.MENUS)
        self.assertEqual(calls[1]['response_schema'],output_formats.RECIPE)

    def test_no_hidden_retry_on_fast_default(self):
        ai=KitchenAI();calls=[]
        class Model:
            def create_chat_completion(self,**kwargs):
                calls.append(kwargs)
                return {'choices':[{'message':{'content':'incomplete {'}}]}
        ai._load=lambda kind:Model()
        with patch.object(config,'AI_ATTEMPTS',1),self.assertRaises(schema.OutputError):
            ai._ask('llm','test',schema.menus)
        self.assertEqual(len(calls),1)
        self.assertEqual(ai.cache,{})

if __name__=='__main__':unittest.main()
