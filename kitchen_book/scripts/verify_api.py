#!/usr/bin/env python3
"""Kitchen recipe API verifier.
Run server first. Uses stdlib HTTP.
"""
import argparse, base64, json, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))



def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--mode',choices=['demo','live'],default='demo')
    parser.add_argument('--image',type=Path,help='실제 촬영 JPEG; live A3와 A2용')
    parser.add_argument('--ingredients',default='달걀,토마토,양파',help='A4용 사용자가 확인한 재료. A3 결과를 자동 확정하지 않음')
    parser.add_argument('--output',type=Path,default=Path('api_validation.json'))
    parser.add_argument('--timeout',type=float,default=600)
    parser.add_argument('--require-all',action='store_true',help='SKIP도 비정상 종료(2)')
    parser.add_argument('--quick',action='store_true',help='모델 추론 생략')
    parser.add_argument('--device',metavar='IP',help='실제 Pi 영상 및 출력 시험')
    args=parser.parse_args(); results=[];token='';latencies={}
    def http(path,data=None,token_override=None):
        headers={'Content-Type':'application/json','X-Kitchen-Token':token if token_override is None else token_override}
        req=Request(args.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urlopen(req,timeout=20) as res:
                raw=res.read();return res.status,json.loads(raw) if 'json' in res.headers.get('Content-Type','') else raw.decode()
        except HTTPError as exc:
            return exc.code,json.loads(exc.read())
    def check(code,fn):
        try:
            detail=fn(); result={'id':code,'status':'PASS','detail':detail or ''}
        except Exception as exc: result={'id':code,'status':'FAIL','detail':str(exc)}
        results.append(result);print(result['status'],code,result['detail'],flush=True)
    def require(condition,message):
        if not condition: raise AssertionError(message)
    def job(path,data):
        start=time.monotonic();status,value=http(path,data);require(status==202,f'{status}: {value}')
        while time.monotonic()-start<args.timeout:
            status,record=http('/api/jobs/'+value['job_id']);require(status==200,str(record))
            if record['status']=='done':
                latencies[path]=record.get('elapsed_seconds');return record['result']
            require(record['status']!='error',str(record));time.sleep(.15)
        raise TimeoutError(path)
    status,health=http('/api/health');require(status==200,'서버 health 오류');token=health['csrf']
    check('A1.mode',lambda:require(health['demo']==(args.mode=='demo'),'--mode와 서버 --demo 설정 불일치'))
    check('A1.screen',lambda:require('stage4' in http('/')[1],'4단계 화면 없음'))
    check('A3.invalid_image',lambda:require(http('/api/ingredients',{'image':'bad'})[0]==400,'400 필요'))
    check('A4.empty_ingredients',lambda:require(http('/api/menus',{'ingredients':[]})[0]==400,'400 필요'))
    check('A1.token',lambda:require(http('/api/menus',{'ingredients':['달걀']},'wrong')[0]==403,'403 필요'))
    fixture=Path(__file__).resolve().parents[1]/'source/tests/camera_fixture.jpg'
    image_path=args.image or (fixture if args.mode=='demo' else None)
    image='data:image/jpeg;base64,'+base64.b64encode(image_path.read_bytes()).decode() if image_path else None
    if image and not args.quick:
        check('A3.capture',lambda:require(isinstance(job('/api/ingredients',{'image':image})['ingredients'],list),'ingredients 목록 없음'))
    else:
        results.append({'id':'A3.capture','status':'SKIP','detail':'--image 실제 사진 필요'})
    if args.mode=='live' and image and health['models']['gesture']['exists']:
        def gesture_check():
            status,result=http('/api/gesture',{'image':image});require(status==200 and 'gesture' in result and not result.get('busy'),str(result))
            return '실사진 단일 프레임 스모크; 손 인식률은 별도 검증'
        check('A2.gesture',gesture_check)
    else:
        results.append({'id':'A2.gesture','status':'SKIP','detail':'실제 gesture 모델과 --image 필요. 실제 손 정확도는 별도 확인'})
    items=[x.strip() for x in args.ingredients.split(',') if x.strip()]
    def generation():
        menus=job('/api/menus',{'ingredients':items})['menus'];require(len(menus)==3,'3개 추천 필요')
        recipe=job('/api/recipe',{'ingredients':items,'menu':menus[0]});require(len(recipe['steps'])>0,'단계 없음')
        return '사용자 확인 재료 → 메뉴 → 레시피 JSON'
    if not args.quick: check('A4.generate',generation)
    check('Pi.invalid',lambda:require(http('/api/device/state',{'mode':'bad'})[0]==400,'400 필요'))
    if not health.get('device'):
        check('Pi.unconfigured',lambda:require(http('/api/device/frame')[0]==502,'502 필요'))
    if args.device:
        require(args.device==health.get('device'),'서버와 검증에 같은 --device IP를 사용하세요')
        def frame():
            with urlopen(args.url+'/api/device/frame',timeout=8) as response:
                raw=response.read()
                require(raw.startswith(bytes.fromhex('ffd8')) and raw.endswith(bytes.fromhex('ffd9')),'JPEG 오류')
        check('Pi.frame',frame)
        for mode in ('step','running','finished','idle'):
            check('Pi.'+mode,lambda m=mode:require(http('/api/device/state',dict(page=1,total=3,seconds=5,mode=m))[0]==200,'Pi 출력 오류'))
            time.sleep(1)
    for result in results:
        if result['status']=='SKIP':print('SKIP',result['id'],result['detail'])
    summary={key:sum(x['status']==key for x in results) for key in ('PASS','FAIL','SKIP')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'mode':args.mode,'version':health['version'],'physical_webcam_verified':False,'summary':summary,'job_seconds':latencies,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary),str(args.output))
    return 1 if summary['FAIL'] else 2 if args.require_all and summary['SKIP'] else 0

if __name__=='__main__':raise SystemExit(main())
