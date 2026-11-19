"""Kitchen tool definitions and common rules for spoken and typed device commands."""
import json

ACTIONS = {1: ('capture',), 2: ('replace', 'recommend'), 3: ('select',), 4: ('next', 'previous')}
PROMPT = """한국어 주방 명령을 JSON으로 분류하세요. /no_think
tool은 move(실행), describe(현재 단계 설명), ask(되묻기) 중 하나입니다.
args.action은 capture=사진 촬영, replace=재료 교체, recommend=재료 확인 후 메뉴 추천,
select=메뉴 선택, next=다음 조리 단계, previous=이전 조리 단계, none=설명 또는 질문입니다.
교체는 old와 new에 조사 없는 재료명을, 메뉴 선택은 index에 1부터 시작하는 번호를 넣으세요.
나머지 문자열은 빈 값, 미사용 번호는 0입니다. 불분명하거나 지원하지 않는 요청은 ask로 한국어 질문을 반환하세요.
'감자가 아니라 양파야'는 replace, old=감자, new=양파입니다. '지금 뭐 해야 해?'는 describe입니다."""
ARGS = {'action': {'type':'string','enum':['none'] + [a for actions in ACTIONS.values() for a in actions]},
        'old': {'type':'string'}, 'new': {'type':'string'}, 'index': {'type':'integer'}}
SCHEMA = {'type':'object','properties':{'tool':{'type':'string','enum':['move','describe','ask']},
          'args':{'type':'object','properties':ARGS,'required':list(ARGS)},'message':{'type':'string'}},
          'required':['tool','args','message']}


def build_context(data):
    text = data.get('text')
    stage = data.get('stage')
    if not isinstance(text, str) or not 0 < len(text.strip()) <= 300 or type(stage) is not int or stage not in ACTIONS:
        raise ValueError('명령 또는 화면 단계가 올바르지 않습니다.')
    context = {'text': text.strip(), 'stage':stage}
    for key, limit in [('ingredients',30), ('menus',3)]:
        items = data.get(key, [])
        if not isinstance(items,list) or len(items)>limit or not all(isinstance(x,str) and 0 < len(x)<=80 for x in items):
            raise ValueError('화면 목록을 확인해 주세요.')
        context[key] = items
    return context


def decide(context, result):
    def ask(message):
        return dict(tool='ask', args={}, message=message)
    if not isinstance(result,dict):
        raise ValueError('기기 명령 형식 오류')
    tool, args = result.get('tool'), result.get('args')
    if tool == 'describe':
        return dict(tool=tool,args={},message='')
    if tool == 'ask':
        return ask(str(result.get('message') or '어떤 동작을 할까요?')[:200])
    if tool != 'move' or not isinstance(args,dict):
        return ask('명령을 다시 말해 주세요.')
    action = args.get('action')
    if action not in ACTIONS[context['stage']]:
        return ask('현재 화면에서는 실행할 수 없어요. 원하는 작업을 다시 말해 주세요.')
    clean = {'action':action}
    if action == 'replace':
        old, new = args.get('old'), args.get('new')
        if old not in context['ingredients'] or not isinstance(new,str) or not 0 < len(new.strip()) <= 40 or any(c in new for c in ',，\r\n'):
            return ask('목록에 있는 어떤 재료를 무엇으로 바꿀까요?')
        clean.update(old=old,new=new.strip())
    if action == 'select':
        index = args.get('index')
        if type(index) is not int or not 1 <= index <= len(context['menus']):
            return ask('몇 번째 메뉴로 레시피를 만들까요?')
        clean['index'] = index
    return dict(tool='move',args=clean,message='')
