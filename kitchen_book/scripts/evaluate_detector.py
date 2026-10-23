"""Run on the user's held-out FOOD-INGREDIENTS data. Never invent accuracy."""
import argparse,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--model',default='models/best.pt');p.add_argument('--device',default='0');p.add_argument('--split',choices=['val','test'],default='test');p.add_argument('--output',default='detector_metrics.json');args=p.parse_args()
    from ultralytics import YOLO
    model=YOLO(args.model)
    if len(model.names)!=120:raise ValueError('120클래스 모델이 아닙니다.')
    results=model.val(data=args.data,split=args.split,imgsz=640,device=args.device)
    metrics={'model':args.model,'data':args.data,'split':args.split,'classes':model.names,'metrics':results.results_dict,'speed_ms':results.speed}
    Path(args.output).write_text(json.dumps(metrics,ensure_ascii=False,indent=2,default=float),encoding='utf-8')
    print(args.output)
if __name__=='__main__':main()
