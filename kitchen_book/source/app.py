#!/usr/bin/env python3
"""FastAPI localhost appliance; preserve v1.2 endpoints and job polling."""
import argparse
import importlib.util
import json
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
import mimetypes

mimetypes.add_type("text/javascript", ".js")

import config
import schema
from ai import KitchenAI, decode_image
from gestures import GestureEngine
from jobs import Jobs
from workflow import validate_request



def create_app(demo=False, ai=None, gesture=None):
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, FileResponse
    from starlette.concurrency import run_in_threadpool
    jobs=Jobs(ai or KitchenAI(demo)); gesture=gesture or GestureEngine(); token=secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.pool.shutdown(wait=True)
        gesture.close()
        if jobs.ai.model is not None: jobs.ai.model.close()

    app=FastAPI(title='비접촉 레시피북 AI Workflow',version=config.VERSION,lifespan=lifespan)
    app.state.jobs=jobs

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host=request.headers.get('host','').split(':')[0]
        if host not in ('localhost','127.0.0.1','testserver'):
            return JSONResponse({'error':'localhost에서 접속하세요.'},403)
        if request.method=='POST' and request.headers.get('X-Kitchen-Token')!=token:
            return JSONResponse({'error':'페이지를 새로고침하세요.'},403)
        if request.method=='POST':
            # Limit streaming bodies as well as Content-Length before JSON parsing.
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>4_200_000: return JSONResponse({'error':'request_too_large'},413)
            request._body=bytes(raw)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.exception_handler(ValueError)
    async def value_error(request,exc):
        return JSONResponse({'error':str(exc)},400)

    @app.get('/',name='A1 화면')
    async def index(): return FileResponse(config.SOURCE/'static/index.html')

    @app.get('/api/health',name='A1 상태')
    async def health():
        return {'version':config.VERSION,'demo':demo,'models':config.model_status(),'csrf':token,
                'detector':config.DETECTOR,'yolo_device':config.YOLO_DEVICE,'gpu_layers':config.GPU_LAYERS}

    @app.get('/api/jobs/{job_id}',name='A3-A5 작업 조회')
    async def job(job_id:str):
        value=jobs.get(job_id)
        return JSONResponse(value or {'error':'job_not_found'},200 if value else 404)

    async def payload(request):
        try: value=await request.json()
        except (ValueError,UnicodeError): raise ValueError('invalid_json')
        if not isinstance(value,dict): raise ValueError('JSON 객체가 필요합니다.')
        return value

    def submit(kind,data):
        try: return JSONResponse({'job_id':jobs.submit(kind,data)},202)
        except BlockingIOError as exc: return JSONResponse({'error':str(exc)},409)

    @app.post('/api/gesture',name='A2 제스처')
    async def recognize(request: Request):
        data=await payload(request)
        decode_image(data.get('image'))
        try: return await run_in_threadpool(gesture.recognize,data['image'])
        except (ImportError,FileNotFoundError) as exc: return JSONResponse({'error':str(exc)},503)
        except Exception as exc:
            logging.exception('Gesture inference failed')
            return JSONResponse({'error':str(exc)},500)

    @app.post('/api/ingredients',name='A3 식재료 탐지')
    async def ingredients(request: Request):
        data=await payload(request); decode_image(data.get('image'))
        return submit('ingredients',data)

    async def generate(request,kind):
        data=await payload(request)
        data['ingredients']=schema.strings(data.get('ingredients'),'확인 재료',1,30)
        if not isinstance(data.get('request',''),str) or len(data.get('request',''))>600: raise ValueError('요청은 600자 이하입니다.')
        if kind=='recipe':
            menu=data.get('menu')
            if not isinstance(menu,dict): raise ValueError('메뉴를 선택하세요.')
            data['menu']={'name':schema.string(menu.get('name'),'메뉴명',80),'missing':schema.strings(menu.get('missing',[]),'추가 재료',0,20)}
        return submit(kind,data)

    @app.post('/api/menus',name='A4 메뉴 추천')
    async def menus(request: Request): return await generate(request,'menus')

    @app.post('/api/recipe',name='A4 레시피 생성')
    async def recipe(request: Request): return await generate(request,'recipe')

    @app.post('/api/llm-answer',name='A5 의도 파악·도구 호출')
    async def llm_answer(request: Request):
        return submit('intent',validate_request(await payload(request)))

    @app.get('/{filename}',include_in_schema=False)
    async def static_file(filename:str):
        if filename not in ('app.js','core.js','style.css'): return JSONResponse({'error':'not_found'},404)
        return FileResponse(config.SOURCE/'static'/filename)
    return app


def diagnostics():
    modules={name:importlib.util.find_spec(name) is not None for name in ('PIL','numpy','fastapi','uvicorn','mediapipe','llama_cpp','ultralytics','torch')}
    status={'version':config.VERSION,'models_dir':str(config.MODELS),'models':config.model_status(),'packages':modules}
    if modules['torch']:
        import torch
        status['torch']={'version':torch.__version__,'cuda_available':torch.cuda.is_available(),'cuda_build':torch.version.cuda}
        if torch.cuda.is_available():
            try:
                value=(torch.ones(16,device='cuda')*2).sum().item()
                status['torch'].update({'gpu':torch.cuda.get_device_name(0),'capability':torch.cuda.get_device_capability(0),'kernel_smoke_pass':value==32})
            except Exception as exc: status['torch']['error']=str(exc)
    if modules['llama_cpp']:
        import llama_cpp
        status['llama_cpp']={'version':llama_cpp.__version__,'gpu_offload':bool(llama_cpp.llama_supports_gpu_offload())}
    return status


def main():
    parser=argparse.ArgumentParser(description='비접촉 AI 레시피북 1.3.0')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--demo',action='store_true',help='고정 예시와 규칙 검사. 실제 모델 추론 아님.')
    parser.add_argument('--check',action='store_true',help='모델·패키지·GPU 진단')
    args=parser.parse_args()
    if args.check:
        status=diagnostics(); print(json.dumps(status,ensure_ascii=False,indent=2))
        required=['llm','gesture']+(['yolo'] if config.DETECTOR=='yolo' or (config.DETECTOR=='auto' and status['models']['yolo']['exists']) else ['vlm','projector'])
        ok=all(status['models'][k]['exists'] for k in required) and all(status['packages'][k] for k in ('PIL','numpy','fastapi','uvicorn','mediapipe','llama_cpp'))
        if 'yolo' in required:
            ok=ok and status['packages']['ultralytics']
            if config.YOLO_DEVICE!='cpu': ok=ok and status.get('torch',{}).get('kernel_smoke_pass',False)
        if config.GPU_LAYERS!=0: ok=ok and status.get('llama_cpp',{}).get('gpu_offload',False)
        raise SystemExit(0 if ok else 1)
    import uvicorn
    print(f'비접촉 레시피북 {config.VERSION} http://127.0.0.1:{args.port} | '+('DEMO 예시 모드' if args.demo else '로컬 AI 모드'),flush=True)
    uvicorn.run(create_app(args.demo),host='127.0.0.1',port=args.port,log_level='info')

if __name__=='__main__': main()
