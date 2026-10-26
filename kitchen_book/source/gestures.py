"""Independent recognizer lock: recipe generation never holds it."""
import threading
import config
from ai import decode_image

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
            if not result.gestures:
                return {'gesture': 'None', 'score': 0}
            category = result.gestures[0][0]
            return {'gesture': category.category_name, 'score': float(category.score)}
        finally:
            self.lock.release()
