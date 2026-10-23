"""Paths are relative to this file, never to the working directory."""
import os
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parent
MODELS = Path(os.environ.get('KITCHEN_MODELS', ROOT / 'models')).expanduser().resolve()
MODEL_FILES = {
    'vlm': os.environ.get('KITCHEN_VLM', 'Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf'),
    'projector': os.environ.get('KITCHEN_PROJECTOR', 'mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf'),
    'llm': os.environ.get('KITCHEN_LLM', 'Qwen3-4B-Q4_K_M.gguf'),
    'gesture': os.environ.get('KITCHEN_GESTURE', 'gesture_recognizer.task'),
}
THREADS = max(1, int(os.environ.get('KITCHEN_THREADS', min(6, os.cpu_count() or 2))))
GPU_LAYERS = int(os.environ.get('KITCHEN_GPU_LAYERS', '0'))

def model_path(kind):
    path = MODELS / MODEL_FILES[kind]
    if not path.is_file():
        raise FileNotFoundError(f'{kind} 모델 없음: {path}. source/README.md의 모델 설정을 확인하세요.')
    return path

def model_status():
    return {k: {'file': v, 'exists': (MODELS / v).is_file()} for k, v in MODEL_FILES.items()}

# Low-memory appliance defaults. Set before starting the server.
IMAGE_SIDE = max(224, min(896, int(os.environ.get('KITCHEN_IMAGE_SIDE', '448'))))
VERIFY_IMAGE = os.environ.get('KITCHEN_VERIFY_IMAGE', '0') == '1'
AI_ATTEMPTS = max(1, min(2, int(os.environ.get('KITCHEN_AI_ATTEMPTS', '1'))))
CONTEXT_SIZE = int(os.environ.get('KITCHEN_CONTEXT', '4096'))

MODEL_FILES['yolo'] = os.environ.get('KITCHEN_YOLO', 'best.pt')
DETECTOR = os.environ.get('KITCHEN_DETECTOR', 'auto').lower()
if DETECTOR not in ('auto', 'yolo', 'vlm'): raise ValueError('KITCHEN_DETECTOR: auto/yolo/vlm')
YOLO_SIZE = int(os.environ.get('KITCHEN_YOLO_SIZE', '640'))
YOLO_CONF = float(os.environ.get('KITCHEN_YOLO_CONF', '.10'))
YOLO_ACCEPT = float(os.environ.get('KITCHEN_YOLO_ACCEPT', '.30'))
YOLO_IOU = float(os.environ.get('KITCHEN_YOLO_IOU', '.5'))
YOLO_DEVICE = os.environ.get('KITCHEN_YOLO_DEVICE', 'cpu')
if not 0 <= YOLO_CONF <= YOLO_ACCEPT <= 1: raise ValueError('YOLO thresholds must satisfy 0 <= conf <= accept <= 1')
VERSION = '1.3.0'
