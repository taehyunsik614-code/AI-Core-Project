"""Inspect actual trained labels; never assume dataset class order."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--model',default='models/best.pt');p.add_argument('--output',default='models/class_names.json');a=p.parse_args()
from ultralytics import YOLO
names=YOLO(a.model).names
if len(names)!=120:raise ValueError(f'120 classes expected, got {len(names)}')
Path(a.output).write_text(json.dumps(names,ensure_ascii=False,indent=2),encoding='utf-8');print(a.output)
