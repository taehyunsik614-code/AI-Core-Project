import json
import sys
import threading
import unittest
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'source'), str(ROOT/'raspberrypi')]
import app
import camera_server
from kitchen_commands import decide


class VoiceRelayTest(unittest.TestCase):
    def test_pc_to_device_command_and_poll(self):
        mic, selector = Mock(), Mock()
        mic.snapshot.return_value = dict(session='a', seq=1, text='다음 단계', status='준비')
        selector.infer.return_value = dict(tool='move', args=dict(action='next'), message='')
        with ExitStack() as stack:
            def start(handler):
                server = ThreadingHTTPServer(('127.0.0.1',0),handler)
                stack.callback(server.server_close)
                threading.Thread(target=server.serve_forever,daemon=True).start()
                stack.callback(server.shutdown)
                return server.server_port
            pi = start(camera_server.handler(None,None,mic,selector))
            pc = start(app.make_handler(True,'127.0.0.1'))
            import http.client
            original = http.client.HTTPConnection
            def connection(ip, port, **opts):
                return original(ip, pi if port==8080 else port, **opts)
            with patch.object(app.device.http.client,'HTTPConnection',side_effect=connection):
                # urllib itself also uses HTTPConnection; use original for the test client.
                def call(path,payload=None,token=''):
                    conn=original('127.0.0.1',pc)
                    conn.request('GET' if payload is None else 'POST',path,
                                 json.dumps(payload).encode() if payload is not None else None,
                                 {'X-Kitchen-Token':token})
                    res=conn.getresponse()
                    self.assertEqual(res.status,200)
                    data=json.loads(res.read());conn.close()
                    return data
                token=call('/api/health')['csrf']
                self.assertEqual(call('/api/voice-poll'),mic.snapshot.return_value)
                for source in ['voice','device']:
                    data=call('/api/device/command',dict(text='다음 단계',source=source,stage=4),token)
                    self.assertEqual(data['args'],{'action':'next'})
                self.assertEqual(call('/api/device/command',dict(text='다음',source='voice',stage=2),token)['tool'],'ask')

    def test_missing_ingredient(self):
        self.assertEqual(decide({'stage':2,'ingredients':['감자']},
                         {'tool':'move','args':{'action':'replace','old':'달걀','new':'양파'}})['tool'],'ask')
