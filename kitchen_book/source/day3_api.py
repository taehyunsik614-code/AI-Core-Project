"""Specification diagnostics use the same configured device as the recipe dashboard."""
import http.client
import io
import json

from PIL import Image
import config
import day3
import device


class Diagnostics:
    def __init__(self, pi, jobs):
        self.pi, self.jobs, self.detector = pi, jobs, None

    def image(self, path, raw):
        if not raw:
            raise ValueError('empty_image')
        try:
            with Image.open(io.BytesIO(raw)) as im:
                if im.format!='JPEG' or im.width*im.height>16_000_000:
                    raise ValueError()
                frame=im.convert('RGB')
        except Exception as exc:
            raise ValueError('invalid_image') from exc
        def predict():
            if path.endswith('yolo-detect'):
                if self.detector is None:
                    from ultralytics import YOLO
                    weights=config.MODELS/'yolo11n.pt'
                    if not weights.is_file():
                        weights=config.ROOT.parent/'yolo11n.pt'
                    if not weights.is_file():
                        raise FileNotFoundError('물체 인식 가중치를 준비하세요.')
                    self.detector=YOLO(str(weights))
                res=self.detector(frame,verbose=False)[0]
                return {'objects':[{'label':res.names[int(b.cls.item())], 'confidence':float(b.conf.item()),
                                     'box':b.xyxy[0].tolist()} for b in res.boxes]}
            def validate(data):
                from schema import string
                return {'description':string(data.get('description'),'장면 설명',500)}
            return self.jobs.ai._ask('vlm','사진을 한국어 두세 문장으로 설명하고 장애물 유무를 적으세요. description 키에 답하세요.',
                                     validate,frame,response_schema={'type':'object','properties':{'description':{'type':'string'}},'required':['description']})
        return self.jobs.pool.submit(predict).result()

    def answer(self, data, mode):
        ctx,history=day3.context(data,mode)
        local=data.get('source','text')=='text'
        packet={'mode':mode,'user_content':json.dumps(ctx,ensure_ascii=False),'history':history}
        if local:
            def predict():
                return day3.infer(self.jobs.ai._load('llm'),packet['user_content'],history)
            prediction=self.jobs.pool.submit(predict).result()
        else:
            if data.get('source') not in ('device','voice'):
                raise ValueError('명령 출처 오류')
            self.target(data.get('ip'))
            try:
                prediction=json.loads(device.relay(self.pi,'/llm-infer',packet,timeout=180))
            except (OSError,http.client.HTTPException) as exc:
                raise ConnectionError('기기 명령 해석 연결이 끊겼습니다. 연결을 확인한 뒤 다시 전송하세요.') from exc
        return day3.decide(ctx,prediction,local)

    def target(self, ip):
        if ip is not None:
            if device.device_ip(ip)!=self.pi:
                raise ConnectionError('등록한 기기에 연결할 수 없습니다.')
        if not self.pi:
            raise ConnectionError('라즈베리파이 연결을 확인하세요.')

    def output(self,path,data):
        self.target(data.get('ip'))
        d=data.get('direction')
        if d not in ('left','right','up','down'):
            raise ValueError('invalid_request')
        if path.endswith('oled-display'):
            return json.loads(device.relay(self.pi,'/oled-display?text='+d.upper()))
        if d in ('left','right'):
            pin='17' if d=='right' else '27'
            return json.loads(device.relay(self.pi,'/gpio-blink?pin='+pin))
        return {'ok':True}

    def stream(self, handler):
        conn=http.client.HTTPConnection(self.pi,8080,timeout=5)
        try:
            conn.request('GET','/stream.mjpg')
            res=conn.getresponse()
            if res.status!=200:
                raise ConnectionError('영상 연결 실패')
            handler.send_response(200)
            handler.send_header('Content-Type',res.getheader('Content-Type'))
            handler.end_headers()
            try:
                while chunk:=res.read1(65536):
                    handler.wfile.write(chunk)
            except OSError:
                pass
        finally:
            conn.close()

    def asset(self, handler, path):
        name=path.removeprefix('/mediapipe/')
        if name=='gesture_recognizer.task':
            file=config.model_path('gesture')
        else:
            root=(config.ROOT/'node_modules/@mediapipe/tasks-vision').resolve()
            file=(root/name).resolve()
            if root not in file.parents or file.suffix not in ('.mjs','.js','.wasm'):
                return handler.send(404,{'error':'경로 없음'})
        if not file.is_file():
            return handler.send(404,{'error':'파일 없음'})
        handler.send(200,file.read_bytes(),'application/wasm' if file.suffix=='.wasm' else
                     'application/octet-stream' if file.suffix=='.task' else 'text/javascript')
