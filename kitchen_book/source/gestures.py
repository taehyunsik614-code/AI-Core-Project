"""Independent recognizer lock: recipe generation never holds it."""
import math
import threading
import config
from ai import decode_image

def landmark_pose(points):
    """Use finger straightness and wrist-relative reach in 3D hand coordinates."""
    if len(points) != 21:
        return None
    xyz = [(p.x,p.y,p.z) for p in points]
    fingers = []
    for base in (5,9,13,17):
        mcp,pip,dip,tip = xyz[base:base+4]
        length = math.dist(mcp,pip)+math.dist(pip,dip)+math.dist(dip,tip)
        ratio = math.dist(mcp,tip)/max(length,1e-8)
        extended = ratio > .88 and math.dist(xyz[0],tip) > math.dist(xyz[0],pip)*1.12
        folded = ratio < .76 or math.dist(xyz[0],tip) < math.dist(xyz[0],pip)*1.02
        fingers.append('open' if extended else 'folded' if folded else 'unknown')
    if fingers == ['open']*4:
        return 'Open_Palm'
    if fingers == ['open','folded','folded','folded']:
        return 'Pointing_Up'
    return None

class GestureEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.recognizer = None

    def recognize(self, image_data):
        if not self.lock.acquire(blocking=False):
            return {'gesture': 'None', 'score': 0, 'busy': True}
        try:
            import mediapipe as mp
            import numpy as np
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            if self.recognizer is None:
                self.recognizer = vision.GestureRecognizer.create_from_options(
                    vision.GestureRecognizerOptions(
                        base_options=python.BaseOptions(model_asset_buffer=config.model_path('gesture').read_bytes()),
                        running_mode=vision.RunningMode.IMAGE, num_hands=1))
            image = decode_image(image_data)
            result = self.recognizer.recognize(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(image)))
            category = result.gestures[0][0] if result.gestures and result.gestures[0] else None
            name = category.category_name if category else 'None'
            score = float(category.score) if category else 0.
            if name in ('None','Unknown') or score < .65:
                hands = result.hand_world_landmarks
                pose = landmark_pose(hands[0]) if hands else None
                if pose:
                    return {'gesture':pose,'score':.75,'source':'landmarks'}
            return {'gesture': name, 'score': score}
        finally:
            self.lock.release()
