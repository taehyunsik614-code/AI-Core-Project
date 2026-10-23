"""Adapter contract with a fake MediaPipe module, NOT physical recognition accuracy."""
import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gestures import GestureEngine

class VideoAdapterTests(unittest.TestCase):
    def test_video_monotonic_and_close(self):
        calls=[];options=[]
        recognizer=SimpleNamespace(recognize_for_video=lambda image,stamp:calls.append(stamp) or SimpleNamespace(gestures=[],hand_landmarks=[]),close=lambda:calls.append('closed'))
        vision=SimpleNamespace(RunningMode=SimpleNamespace(VIDEO='VIDEO'),GestureRecognizerOptions=lambda **k:options.append(k) or k,
            GestureRecognizer=SimpleNamespace(create_from_options=lambda o:recognizer))
        python=SimpleNamespace(BaseOptions=lambda **k:k,vision=vision)
        mp=SimpleNamespace(Image=lambda **k:k,ImageFormat=SimpleNamespace(SRGB='RGB'),tasks=SimpleNamespace(python=python))
        path=SimpleNamespace(read_bytes=lambda:b'model')
        modules={'mediapipe':mp,'mediapipe.tasks':mp.tasks,'mediapipe.tasks.python':python,'mediapipe.tasks.python.vision':vision}
        with patch.dict(sys.modules,modules),patch('gestures.config.model_path',return_value=path),patch('gestures.decode_image',return_value=[[1]]),patch('gestures.time.monotonic_ns',return_value=1000000):
            g=GestureEngine();self.assertFalse(g.recognize('fake')['hand_present']);g.recognize('fake');g.close()
        self.assertEqual(calls,[1,2,'closed']);self.assertEqual(options[0]['running_mode'],'VIDEO')
    def test_busy_does_not_block(self):
        g=GestureEngine();g.lock.acquire()
        try:self.assertTrue(g.recognize('unused')['busy'])
        finally:g.lock.release()
if __name__=='__main__':unittest.main()
