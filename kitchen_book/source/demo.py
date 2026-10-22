"""Explicit fixtures, used only with --demo. Never passed off as inference."""

def result(kind, payload):
    if kind == 'ingredients':
        return {'ingredients': ['달걀', '토마토', '대파'], 'uncertain': ['데모 고정 재료입니다. 실제 사진 인식이 아닙니다.']}
    if kind == 'menus':
        return {'menus': [
            {'id': '1', 'name': '토마토 달걀볶음', 'reason': '데모 예시: 부드러운 달걀과 토마토의 조합', 'missing': ['식용유', '소금']},
            {'id': '2', 'name': '대파 달걀볶음밥', 'reason': '데모 예시: 한 그릇 요리', 'missing': ['밥', '간장', '식용유']},
            {'id': '3', 'name': '토마토 달걀국', 'reason': '데모 예시: 따뜻한 국물 요리', 'missing': ['물', '소금']} ]}
    name = payload['menu']['name']
    return {'title': name + ' (동작 확인용 데모)', 'ingredients': ['달걀 2개', '토마토 1개', '대파 1/4대', '식용유 1큰술', '소금 약간'],
            'steps': [
                {'title': '재료 손질', 'instruction': '토마토를 씻어 한입 크기로 자르고 대파를 썹니다. 달걀을 풀어 둡니다.', 'timer_seconds': 0},
                {'title': '달걀 볶기', 'instruction': '팬에 기름을 두르고 달걀을 저어 충분히 익힌 뒤 잠시 덜어 둡니다. 이 타이머는 동작 확인용입니다.', 'timer_seconds': 60},
                {'title': '토마토 볶기', 'instruction': '대파와 토마토를 볶아 부드럽게 만듭니다. 화력과 재료 크기에 따라 익힘 상태를 확인하세요.', 'timer_seconds': 180},
                {'title': '함께 마무리', 'instruction': '달걀을 넣고 소금으로 간한 뒤 가볍게 섞습니다.', 'timer_seconds': 30}],
            'notes': ['데모에서는 선택 메뉴와 무관하게 동일한 예시 조리 단계가 표시됩니다.', '실제 레시피는 일반 모드에서 LLM이 생성합니다.']}
