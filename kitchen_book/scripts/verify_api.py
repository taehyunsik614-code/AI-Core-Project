#!/usr/bin/env python3
"""A1-A5, R1-R5 verifier. Demo != real model or physical camera validation.
Run server first. Uses stdlib HTTP; direct rule tests import source/workflow.py.
"""
import argparse, base64, json, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from workflow import parse_tool_call, apply_rules, validate_request


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--mode',choices=['demo','live'],default='demo')
    parser.add_argument('--image',type=Path,help='실제 촬영 JPEG; live A3와 A2용')
    parser.add_argument('--ingredients',default='달걀,토마토,양파',help='A4용 사용자가 확인한 재료. A3 결과를 자동 확정하지 않음')
    parser.add_argument('--output',type=Path,default=Path('api_validation.json'))
    parser.add_argument('--timeout',type=float,default=600)
    parser.add_argument('--require-all',action='store_true',help='SKIP도 비정상 종료(2)')
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
    check('A1.schema',lambda:require('/api/llm-answer' in http('/openapi.json')[1]['paths'],'OpenAPI 없음'))
    check('A3.invalid_image',lambda:require(http('/api/ingredients',{'image':'bad'})[0]==400,'400 필요'))
    check('A4.empty_ingredients',lambda:require(http('/api/menus',{'ingredients':[]})[0]==400,'400 필요'))
    check('A5.empty_prompt',lambda:require(http('/api/llm-answer',{'prompt':''})[0]==400,'400 필요'))
    check('A1.token',lambda:require(http('/api/menus',{'ingredients':['달걀']},'wrong')[0]==403,'403 필요'))
    fixture=Path(__file__).resolve().parents[1]/'source/tests/camera_fixture.jpg'
    image_path=args.image or (fixture if args.mode=='demo' else None)
    image='data:image/jpeg;base64,'+base64.b64encode(image_path.read_bytes()).decode() if image_path else None
    if image:
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
    check('A4.generate',generation)
    context={'page':1,'total_pages':5,'timer_seconds':180,'step_seconds':120}
    def intent(text,**extra):
        result=job('/api/llm-answer',{'prompt':text,'context':context,**extra})
        require(result['need_more_info']==(result['tool']=='ask'),'R4 불일치')
        require(result['inference_mode']==('demo_rules' if args.mode=='demo' else 'qwen'),'추론 모드 불일치')
        return result
    examples=[('다음 2페이지','page',{'direction':'next','steps':2}),('이전 페이지','page',{'direction':'previous','steps':1}),
              ('타이머 3분 설정','timer',{'action':'set','seconds':180}),('타이머 시작','timer',{'action':'start'}),
              ('타이머 일시정지','timer',{'action':'pause'}),('타이머 초기화','timer',{'action':'reset'}),
              ('타이머 설정','ask',None),('현재 단계 설명해 줘','describe',None)]
    for i,(prompt,tool,expected) in enumerate(examples,1):
        def case(p=prompt,t=tool,e=expected):
            result=intent(p);require(result['tool']==t,str(result));require(e is None or result['args']==e,str(result));return p
        check(f'A5.intent{i}',case)
    def continuation():
        first=intent('2페이지 넘겨');require(first['tool']=='ask',str(first))
        history=[{'role':'user','content':'2페이지 넘겨'},{'role':'assistant',**first}]
        result=intent('이전',history=history);require(result['args']=={'direction':'previous','steps':2},str(result))
    check('R5.continuation',continuation)
    hand={'name':'Thumb_Down','mode':'book','stable':True,'score':.99,'age_ms':100}
    check('F306.conflict',lambda:require(intent('다음 2페이지',gesture=hand)['args']['direction']=='next','텍스트 우선 실패'))
    check('F306.hand',lambda:require(intent('이쪽으로 2페이지',gesture=hand)['args']['direction']=='previous','손 근거 실패'))
    check('F306.stale',lambda:require(intent('이쪽으로 2페이지',gesture={**hand,'age_ms':2000})['tool']=='ask','오래된 손 근거 사용'))
    check('R1.parser',lambda:require(parse_tool_call('{broken')['tool']=='describe','잘못된 JSON fallback 실패'))
    check('R2.clamp',lambda:require(parse_tool_call({'tool':'page','args':{'direction':'next','steps':999}})['args']['steps']==10,'clamp 실패'))
    check('R3.evidence',lambda:require(apply_rules(parse_tool_call({'tool':'page','args':{'direction':'next'}}),validate_request({'prompt':'버스 위치로 가','context':context}))['tool']=='ask','근거 없는 이동'))
    for result in results:
        if result['status']=='SKIP':print('SKIP',result['id'],result['detail'])
    summary={key:sum(x['status']==key for x in results) for key in ('PASS','FAIL','SKIP')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'mode':args.mode,'version':health['version'],'physical_webcam_verified':False,'summary':summary,'job_seconds':latencies,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary),str(args.output))
    return 1 if summary['FAIL'] else 2 if args.require_all and summary['SKIP'] else 0

if __name__=='__main__':raise SystemExit(main())
