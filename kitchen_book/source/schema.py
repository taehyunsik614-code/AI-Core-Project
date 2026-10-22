"""Validate all model outputs before exposing them to the UI."""
import json
import re
from durations import duration_from_text

class OutputError(ValueError):
    pass

def parse_json(raw, allow_array=False):
    text = re.sub(r'<think>.*?(?:</think>|$)', '', raw or '', flags=re.S).strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.I).strip()
    text = re.sub(r'\s*```$', '', text).strip()
    decoder = json.JSONDecoder()
    for match in re.finditer(r'[\{\[]', text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            if match.start() == 0:
                break  # Never salvage an inner object from a truncated root.
            continue
        if isinstance(value, dict) or (allow_array and isinstance(value, list)):
            return value
        if isinstance(value, list):
            raise OutputError('JSON 객체가 필요합니다. 배열만 반환되었습니다.')
    raise OutputError('모델이 완전한 JSON을 생성하지 못했습니다. 다시 시도하세요.')


def string(value, label, limit=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise OutputError(f'{label}: 비어 있지 않은 {limit}자 이하 문자열이어야 합니다.')
    return value.strip()

def strings(values, label, minimum=0, maximum=30):
    if not isinstance(values, list) or not minimum <= len(values) <= maximum:
        raise OutputError(f'{label}: {minimum}~{maximum}개 목록이어야 합니다.')
    return list(dict.fromkeys(string(x, label, 200) for x in values))

def ingredients(data):
    return {'ingredients': strings(data.get('ingredients'), '재료', 0, 30),
            'uncertain': strings(data.get('uncertain', []), '불확실 재료', 0, 20)}

def menus(data):
    values = data.get('menus')
    if not isinstance(values, list) or len(values) != 3:
        raise OutputError('추천 메뉴는 정확히 3개여야 합니다.')
    result = []
    for i, item in enumerate(values):
        if not isinstance(item, dict):
            raise OutputError('메뉴 형식 오류')
        result.append({'id': str(i + 1), 'name': string(item.get('name'), '메뉴명', 80),
                       'reason': string(item.get('reason'), '추천 이유', 300),
                       'missing': strings(item.get('missing', []), '추가 재료', 0, 20)})
    return {'menus': result}

def recipe(data):
    title = string(data.get('title'), '레시피명', 80)
    items = strings(data.get('ingredients'), '재료와 분량', 1, 30)
    steps = data.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 16:
        raise OutputError('레시피는 1~16단계여야 합니다.')
    clean = []
    for item in steps:
        if not isinstance(item, dict):
            raise OutputError('조리 단계 형식 오류')
        instruction = string(item.get('instruction'), '조리 설명', 1000)
        seconds = item.get('timer_seconds', 0)
        # Numeric strings are common structured-output slips. Reject all other types.
        if isinstance(seconds, str) and seconds.strip().isdigit():
            seconds = int(seconds.strip())
        if type(seconds) is not int or not 0 <= seconds <= 86400:
            raise OutputError('타이머는 0~86400 범위의 정수 초여야 합니다.')
        explicit = duration_from_text(instruction)
        if explicit:
            seconds = explicit
        clean.append({'title': string(item.get('title'), '단계명', 80),
                      'instruction': instruction, 'timer_seconds': seconds,
                      'timer_origin': 'instruction' if explicit else 'model' if seconds else 'none'})
    return {'title': title, 'ingredients': items, 'steps': clean,
            'notes': strings(data.get('notes', []), '참고사항', 0, 10)}


def observations(data):
    uncertain = []
    if isinstance(data, list):
        values = data
    elif isinstance(data, dict):
        # Accept complete, equivalent VLM outputs without guessing new ingredients.
        key = next((k for k in ('objects', 'ingredients', '재료') if k in data), None)
        if key is None:
            raise OutputError('재료 목록 필드가 없습니다. 받은 항목: ' + ', '.join(map(str, data.keys())))
        values = data[key]
        uncertain = strings(data.get('uncertain', []), '불확실 항목', 0, 20)
    else:
        raise OutputError('사진 관찰 결과는 목록 또는 JSON 객체여야 합니다.')
    if isinstance(values, dict) and 'name' in values:
        values = [values]
    if not isinstance(values, list):
        raise OutputError('재료 목록이 배열이 아닙니다. 받은 형식: ' + type(values).__name__)
    if len(values) > 12:
        uncertain.append('후보가 많아 처음 12개만 재확인했습니다. 재료를 나누어 촬영하세요.')
    result, seen = [], set()
    for item in values[:12]:
        if isinstance(item, str):
            name = string(item, '재료명', 80)
            evidence = '시각적 특징이 없는 후보입니다. 사진 대조가 필요합니다.'
        elif isinstance(item, dict):
            name = string(item.get('name'), '재료명', 80)
            evidence = string(item.get('evidence') or '시각적 특징이 없는 후보입니다. 사진 대조가 필요합니다.', '시각적 특징', 200)
        else:
            raise OutputError('재료 항목은 이름 또는 이름·특징 객체여야 합니다.')
        if name not in seen:
            result.append({'name': name, 'evidence': evidence})
            seen.add(name)
    return {'objects': result, 'uncertain': uncertain}


def verification(data, names):
    checks = data if isinstance(data, list) else data.get('checks')
    if not isinstance(checks, list) or len(checks) != len(names):
        raise OutputError('모든 재료 후보를 한 번씩 확인해야 합니다.')
    seen, result = set(), []
    for item in checks:
        if not isinstance(item, dict):
            raise OutputError('재확인 형식 오류')
        name = item.get('name')
        if name not in names or name in seen or type(item.get('visible')) is not bool:
            raise OutputError('재확인 후보 또는 판정 형식 오류')
        result.append({'name': name, 'visible': item['visible'], 'evidence': string(item.get('evidence'), '재확인 근거', 200)})
        seen.add(name)
    return result
