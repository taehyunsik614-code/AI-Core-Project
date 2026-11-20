"""Run with the PC server already running. Never equate an API ACK with physical observation."""
import argparse
import json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8000')
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--quick',action='store_true')
mode.add_argument('--device')
parser.add_argument('--image',type=Path,default=Path(__file__).resolve().parents[1]/'source/tests/camera_fixture.jpg')
args=parser.parse_args()
token=''
failed=[]
def call(path,data=None,status=200,base=None,stream=False,mime='application/json'):
    body=json.dumps(data).encode() if isinstance(data,dict) else data
    req=Request((base or args.url)+path,data=body,headers={'X-Kitchen-Token':token,'Content-Type':mime})
    try:
        response=urlopen(req,timeout=200)
    except HTTPError as e:
        response=e
    with response as r:
        if r.status!=status:
            raise ValueError(f'HTTP {r.status} · '+r.read(512).decode(errors='replace'))
        if stream:
            return r.read(100)
        raw=r.read()
        return json.loads(raw) if 'json' in r.headers.get('Content-Type','') else raw

def check(label,fn):
    try:
        if not fn():
            raise ValueError('결과 불일치')
        print('PASS',label,flush=True)
    except Exception as exc:
        print('FAIL',label,exc,flush=True)
        failed.append(label)

def signal(route,d):
    return call('/api/'+route,{'ip':args.device,'direction':d})['ok']

def command(text,source=None,**more):
    data={'prompt':text,**more}
    if source:
        data.update(source=source,ip=args.device)
    return call('/api/llm-answer',data)

health=call('/api/health')
token=health['csrf']
check('A1 화면',lambda:b'html' in call('/'))
for key,route in [('A3','yolo-detect'),('A4','vlm-describe')]:
    check(key+' 잘못된 이미지 400',lambda:call('/api/'+route,b'bad',400,mime='image/jpeg')['error']=='invalid_image')
check('A5 빈 질문 400',lambda:call('/api/llm-answer',{'prompt':''},400)['error'])
check('A9/F303 연결 실패 격리',lambda:call('/api/voice-poll?ip=192.0.2.1',status=502)['error'] and call('/api/health')['csrf']==token)
if not args.quick:
    check('A2 제스처 자산',lambda:all(call('/mediapipe/'+name,stream=True) for name in
        ('vision_bundle.mjs','wasm/vision_wasm_internal.wasm','gesture_recognizer.task')))
    check('A3 실제 물체 인식',lambda:isinstance(call('/api/yolo-detect',args.image.read_bytes(),mime='image/jpeg')['objects'],list))
    check('A4 실제 장면 설명',lambda:bool(call('/api/vlm-describe',args.image.read_bytes(),mime='image/jpeg')['description']))
    check('A5/R10 기본 PC 모델',lambda:'3칸' in command('오른쪽으로 3칸 가')['message'])
if args.device:
    pi='http://'+args.device+':8080'
    check('D1 영상',lambda:b'frame' in call('/stream.mjpg',base=pi,stream=True))
    check('A6 영상 중계',lambda:b'frame' in call('/api/camera-stream?ip='+args.device,stream=True))
    check('D4/A9 발화 번호',lambda:all(isinstance(x.get('seq'),int) for x in
        [call('/voice-text',base=pi),call('/api/voice-poll?ip='+args.device)]))
    check('D5 빈 요청 400',lambda:call('/llm-infer',{},400,base=pi)['error'])
    def describe():
        r=command('앞에 뭐가 보여?', 'device', vlm_description='도마 위에 양파가 있습니다.')
        return r['tool']=='describe' and '양파' in r['message']
    check('F301 장면 설명',describe)
    def kitchen_steps():
        body={'stage':4,'workflow':'day3','source':'device','text':'두 단계 이동해 줘'}
        first=call('/api/device/command',body)
        if first['tool']!='ask':
            return False
        second=call('/api/device/command',dict(body,source='voice',text='다음으로',pending=first['pending'],
                    history=[{'role':'user','content':body['text']},{'role':'assistant','content':first['message']}]))
        return second['tool']=='move' and second['args']=={'direction':'next','steps':2}
    check('F301/F302 주방 텍스트에서 음성 이어가기',kitchen_steps)
    def chain():
        expected=[('right',2),('up',1)]
        for src in ('device','voice'):
            r=command('오른쪽 2칸 가고 위로 1칸',src)
            if r['tool']!='move' or r['need_more_info'] or '칸' in r['message']:
                return False
            if [(a['direction'],a['steps']) for a in [r['args'],r['then']]]!=expected:
                return False
        return True
    check('D5/A5/F301/R1·R2·R9·R10 음성과 텍스트 연속 이동',chain)
    def dialogue():
        r=command('저쪽으로 두 칸 가','voice')
        if not r['need_more_info'] or r['tool']!='ask':
            return False
        history=[{'role':'user','content':'저쪽으로 두 칸 가'},{'role':'assistant','content':r['message']}]
        for reply,wanted in [('왼쪽','left'),('응',r['pending'].get('guess'))]:
            if wanted:
                moved=command(reply,'device',history=history,pending=r['pending'])
                if moved['args']!={'direction':wanted,'steps':2} or moved['need_more_info']:
                    return False
        return True
    check('F302/R3·R4·R5·R7 대화 이어가기',dialogue)
    for d in ('right','up','left','down'):
        check('A8/D3/R8 표시 '+d,lambda:signal('oled-display',d))
        check('A7/D2/R8 신호 '+d,lambda:signal('robot-signal',d))
    check('R6 기기 오류 뒤 로컬 유지',lambda:call('/api/voice-poll?ip=192.0.2.1',status=502)['error'] and '3칸' in command('오른쪽 3칸')['message'])
    print('실물 관찰 별도 · 버튼 녹음, OLED 순서, 좌우 LED, 실제 네트워크 단절 및 복구를 확인하세요.')
elif args.quick:
    print('생략 · 실제 모델 추론과 기기 검사는 빠른 검사 범위 밖입니다.')
else:
    print('생략 · 기기 검사는 --device 옵션으로 실행하세요.')
raise SystemExit(bool(failed))
