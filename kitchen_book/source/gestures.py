"""Independent VIDEO recognizer; monotonically increasing server timestamps."""
import threading
import time
import math
import config
from ai import decode_image


def finger_count(points):
    """Rotation/mirror invariant joint angles; use non-thumb digits + thumb angle.
    This geometric cue is only used by the held timer sequence, not class recognition.
    """
    def angle(a,b,c):
        u=[getattr(a,k)-getattr(b,k) for k in ('x','y','z')]
        v=[getattr(c,k)-getattr(b,k) for k in ('x','y','z')]
        n=math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))
        return math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(u,v))/n)))) if n else 0
    def dist(a,b): return sum((getattr(a,k)-getattr(b,k))**2 for k in ('x','y','z'))
    fingers=sum(angle(points[m],points[p],points[t])>160 and dist(points[t],points[0])>dist(points[p],points[0])*1.1 for m,p,t in [(5,6,8),(9,10,12),(13,14,16),(17,18,20)])
    thumb=angle(points[1],points[2],points[4])>155 and dist(points[4],points[17])>dist(points[3],points[17])*1.25
    return fingers+int(thumb)


class GestureEngine:
    def __init__(self):
        self.lock=threading.Lock(); self.recognizer=None; self.last_timestamp=0

    def close(self):
        with self.lock:
            if self.recognizer is not None: self.recognizer.close(); self.recognizer=None

    def recognize(self,image_data):
        if not self.lock.acquire(blocking=False): return {'gesture':'None','score':0,'busy':True}
        try:
            import mediapipe as mp
            import numpy as np
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            if self.recognizer is None:
                self.recognizer=vision.GestureRecognizer.create_from_options(vision.GestureRecognizerOptions(
                    base_options=python.BaseOptions(model_asset_buffer=config.model_path('gesture').read_bytes()),
                    running_mode=vision.RunningMode.VIDEO,num_hands=1,
                    min_hand_detection_confidence=.6,min_hand_presence_confidence=.6,min_tracking_confidence=.6))
            image=decode_image(image_data,max_side=480)
            self.last_timestamp=max(self.last_timestamp+1,time.monotonic_ns()//1_000_000)
            start=time.perf_counter()
            result=self.recognizer.recognize_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.asarray(image)),self.last_timestamp)
            present=bool(result.hand_landmarks)
            category=result.gestures[0][0] if result.gestures and result.gestures[0] else None
            return {'gesture':category.category_name if category else 'None','score':float(category.score) if category else 0,
                    'hand_present':present,'fingers':finger_count(result.hand_landmarks[0]) if present else 0,
                    'timestamp_ms':self.last_timestamp,'inference_ms':round((time.perf_counter()-start)*1000,1)}
        finally: self.lock.release()
