"""Shared PC rules for the recipe book and the direction demonstration."""
import json
import re

LABEL = dict(next='다음', previous='이전', right='오른쪽', left='왼쪽', up='위', down='아래')
WORDS = {'next':r'다음|앞으로', 'previous':r'이전|뒤로|전 단계',
         'right':r'오른쪽|오른편|우측', 'left':r'왼쪽|왼편|좌측',
         'up':r'위쪽|위로|^위$|상단', 'down':r'아래|밑으로|하단'}
COUNT = {'한':1,'두':2,'세':3,'네':4,'다섯':5,'여섯':6,'일곱':7,'여덟':8,'아홉':9,'열':10}
PROMPT = """당신은 기기 도구 선택기입니다. JSON만 답하세요. /no_think
명령 실행은 move, 질문은 describe, 의도가 모호하면 ask입니다. 주방에서 next/previous는 조리 단계입니다.
기다리는 시간 질문은 describe와 topic=time, 현재 할 일은 describe와 topic=step입니다.
방향 검증에서는 left/right/up/down 중 명시한 방향을 고릅니다. 추측은 guess에만 넣으세요.
두 이동은 순서대로 direction과 second에 넣습니다. 각 steps는 1~10입니다. 방향 없으면 none.
pending은 직전 되묻기입니다. 긍정은 제안 수락, 명시한 다른 방향은 정정입니다."""
direction = {'type':'string','enum':['none',*LABEL]}
props = {'tool':{'type':'string','enum':['move','ask','describe']},'direction':direction,
         'steps':{'type':'integer'},'second':direction,'second_steps':{'type':'integer'},
         'guess':direction,'topic':{'type':'string','enum':['time','step']}}
SCHEMA = {'type':'object','properties':props,'required':list(props),'additionalProperties':False}


def infer(model, content, history):
    reply = model.create_chat_completion(messages=[{'role':'system','content':PROMPT}, *history,
        {'role':'user','content':content+' /no_think'}], temperature=0, max_tokens=160,
        response_format={'type':'json_object','schema':SCHEMA})
    try:
        return json.loads(reply['choices'][0]['message']['content'])
    except (ValueError, TypeError):
        return {}


def steps(n):
    return max(1,min(10,n)) if type(n) is int else 1


def count(text, default):
    match=re.search(r'(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:칸|단계)',text)
    if not match:
        return steps(default)
    word=match[1]
    return steps(int(word) if word.isdigit() else COUNT[word])


def decide(ctx, prediction, local=False):
    text=ctx['text']
    kitchen=ctx['mode']=='kitchen'
    allowed=('next','previous') if kitchen else ('right','left','up','down')
    raw=prediction if isinstance(prediction,dict) else {}
    if isinstance(raw.get('args'),dict):
        raw={**raw['args'],'tool':raw.get('tool')}
    pending=ctx.get('pending') or {}
    tool=raw.get('tool')
    hits=sorted((m.start(),d) for d in allowed for m in re.finditer(WORDS[d],text))
    answer=dict(tool='describe',args={},need_more_info=False,message='',user_content=json.dumps(ctx,ensure_ascii=False))
    if tool not in ('move','ask','describe'):
        return answer
    affirmative=text.strip(' .!?') in ('응','네','예','맞아','그래','좋아','그렇게 해줘')
    accept=affirmative and pending.get('guess') in allowed
    # Clear questions have priority over embedded direction words.
    time_question=kitchen and bool(re.search('얼마나.*기다|몇\s*분|시간.*얼마',text))
    what_question=kitchen and bool(re.search('지금.*(뭐|무엇).*해',text))
    explicit_move=bool(re.search('이동|넘어가|(?:다음|이전)\s*단계[.!? ]*$',text))
    if time_question or what_question or (tool=='describe' and not explicit_move and not accept and not (pending and hits)):
        answer['args']={'topic':'time' if raw.get('topic')=='time' or re.search('얼마나|시간|몇 분',text) else 'step'}
        answer['message']=ctx.get('vlm_description') or '현재 장면에 대한 설명이 없습니다.'
        return answer
    n=count(text,pending.get('steps',raw.get('steps')))
    if hits:
        d=hits[0][1]
    elif accept:
        d=pending['guess']
    else:
        d=ctx.get('gesture_direction')
    if d not in allowed:
        guess=raw.get('guess')
        if guess not in allowed:
            guess='next' if kitchen else raw.get('direction')
        if guess not in allowed and not kitchen and '저쪽' in text:
            guess='right'
        args={'steps':n}
        if guess in allowed:
            args['guess']=guess
        question=(LABEL[guess]+('로' if guess in ('up','down') else '으로')+' 이동할까요?') if guess in allowed else '어느 방향으로 이동할까요?'
        return dict(answer,tool='ask',args=args,pending=args,need_more_info=True,message=question)
    segments=[dict(direction=d,steps=n)]
    if len(hits)>1:
        segments[0]['steps']=count(text[:hits[1][0]],raw.get('steps'))
        segments.append(dict(direction=hits[1][1],steps=count(text[hits[1][0]:],raw.get('second_steps'))))
    result=dict(answer,tool='move',args=segments[0])
    if len(segments)>1:
        result['then']=segments[1]
    result['message']=' → '.join(LABEL[s['direction']]+(f" {s['steps']}칸" if local else '') for s in segments)+' 이동합니다.'
    return result


def context(data, mode):
    text=data.get('text',data.get('prompt'))
    if not isinstance(text,str) or not 0<len(text.strip())<=300:
        raise ValueError('질문을 1~300자로 입력하세요.')
    ctx={'text':text.strip(),'mode':mode}
    for key in ('vlm_description','gesture_direction','yolo_summary'):
        if key in data:
            ctx[key]=str(data[key])[:500]
    pending=data.get('pending') or {}
    if not isinstance(pending,dict):
        raise ValueError('이전 질문 형식 오류')
    ctx['pending']={'steps':steps(pending.get('steps')),'guess':pending.get('guess')} if pending else {}
    history=data.get('history',[])
    if not isinstance(history,list) or len(history)>4 or any(not isinstance(m,dict) or
           m.get('role') not in ('user','assistant') or not isinstance(m.get('content'),str)
           or len(m['content'])>300 for m in history):
        raise ValueError('대화 기록 형식 오류')
    if not pending and len(history)>=2 and history[-1]['role']=='assistant' and history[-2]['role']=='user':
        previous=history[-1]['content']
        if re.search('갈까요|이동할까요|방향',previous):
            possible=('next','previous') if mode=='kitchen' else ('left','right','up','down')
            guesses=[d for d in possible if re.search(WORDS[d],previous)]
            ctx['pending']={'steps':count(history[-2]['content'],1),'guess':guesses[0] if len(guesses)==1 else None}
    return ctx, history
