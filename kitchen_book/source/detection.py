"""YOLO11 ingredient adapter. Class IDs always come from best.pt names metadata."""
import hashlib
import json
import time
import config

class IngredientDetector:
    def __init__(self):
        self.model=None
        self.signature=None
        self.aliases={}

    def detect(self, image):
        path=config.model_path('yolo')
        signature=(str(path),path.stat().st_mtime_ns,path.stat().st_size)
        if self.model is None or signature!=self.signature:
            from ultralytics import YOLO
            self.model=YOLO(str(path),task='detect')
            if len(self.model.names)!=120:
                self.model=None
                raise ValueError('FOOD-INGREDIENTS 120클래스 모델이 아닙니다. 학습 best.pt를 확인하세요.')
            self.signature=signature
            alias_path=config.MODELS/'ingredient_labels_ko.json'
            self.aliases=json.loads(alias_path.read_text(encoding='utf-8')) if alias_path.is_file() else {}
        start=time.perf_counter()
        result=self.model.predict(image,conf=config.YOLO_CONF,iou=config.YOLO_IOU,
                                  imgsz=config.YOLO_SIZE,device=config.YOLO_DEVICE,
                                  max_det=60,verbose=False)[0]
        objects=[]; accepted=[]; uncertain=[]
        if result.boxes is not None:
            for coords,score,cls in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist()):
                label=str(result.names[int(cls)])
                name=self.aliases.get(label,label)
                obj={'class_id':int(cls),'label':label,'name':name,'confidence':round(float(score),4),
                     'box':[round(float(x),1) for x in coords], 'accepted':score>=config.YOLO_ACCEPT}
                objects.append(obj)
                if score>=config.YOLO_ACCEPT: accepted.append(name)
                else: uncertain.append(f'{name} ({score:.0%}) · 낮은 신뢰도 후보')
        return {'ingredients':list(dict.fromkeys(accepted))[:30], 'uncertain':list(dict.fromkeys(uncertain)),
                'objects':objects,'evidence':[{'name':o['name'],'evidence':f"YOLO {o['confidence']:.0%} / 클래스 {o['class_id']}"} for o in objects],
                'backend':'yolo','review_required':True,'verification_status':'yolo_candidates',
                'inference_ms':round((time.perf_counter()-start)*1000,1),
                'image_info':{'width':image.width,'height':image.height,'sha256':hashlib.sha256(image.tobytes()).hexdigest()[:12]}}
