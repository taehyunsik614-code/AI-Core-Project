# F301~F306 구현 대응

프로젝트: 비접촉 AI 레시피북 / 1.3.0 / 2026-10-23

| 번호 | 우리 주제의 요구사항 | 구현 위치 | 현재 판정 |
|---|---|---|---|
| F301 필수 | A1~A5 API, R1~R5 규칙, PASS/FAIL/SKIP 자동 검증 | `app.py`, `workflow.py`, `scripts/verify_api.py`, `docs/API_DESIGN.md` | 구현. 모델 없는 자동 검증 실행 |
| F302 필수 | Qwen3-4B 메뉴·레시피 생성, 의도 파악, page/timer/describe/ask JSON | 기존 `ai.py`, 추가 `workflow.py`, JSON Schema | 코드 및 가짜 모델 어댑터 테스트. 실제 Qwen 추론 미검증 |
| F303 필수 | 근거 없는 페이지/시간 실행 차단, 조건 분기, 되묻기 이어가기 | `parse_tool_call`, `text_evidence`, `apply_rules` | 규칙·HTTP·DOM 검증 |
| F304 필수 | 촬영 → 확인·수정 → 메뉴 → 레시피북, AI 도구와 실제 UI 상태 연결 | `static/index.html`, `app.js`, `core.js` | 가짜 웹캠·DEMO를 이용한 DOM 전체 흐름 검증. 실제 웹캠 미검증 |
| F305 심화 | 손만으로 페이지, 타이머 설정/시작/정지/초기화. 분 설정 시퀀스 | `gestures.py`, `GestureGate`, `TimerSequence`, `dispatchGesture` | 시퀀스·VIDEO 호출 계약·DOM 검증. 실제 손 인식률 미측정 |
| F306 심화 | 텍스트+현재 손 근거, 텍스트 우선, 충돌·손 없음·오래된 손 처리 | `gesture_evidence`, `apply_rules`, `sendCommand` | 규칙·API·DOM 검증. 실제 손+Qwen 결합 미검증 |

명세서의 move/describe/ask, 격자 시뮬레이터는 책 페이지·타이머 도구로 바꿨다. 원본 PDF의 F301~F306을 그대로 충족하는 로봇 프로젝트라는 뜻이 아니라, 사용자 지정 주제에 맞춘 구현이다.

## 기존 코드에서 보존한 부분

- `source/`와 `models/` 형제 구조, `python source\app.py` 실행 진입점.
- 촬영, 재료 확인 체크, 수정 시 확인 취소, 뒤로 가기, 카메라 DOM 이동.
- VLM 사진 분석 및 선택적 2차 확인, Qwen 메뉴 3개·레시피 JSON 출력 검증.
- 직렬 작업 큐, 최대 24개 AI 결과 캐시, 오류 시 DEMO를 섞지 않는 정책.
- 레시피 JSON 저장/불러오기, localStorage 복원, 설명에서 타이머 시간 보정.
- 7개 기본 포즈와 책/타이머 모드, 실행 중 타이머의 페이지 이동 유지.
- 기존 27개 Python 테스트와 7개 JavaScript 상태 테스트. HTTP 테스트 연결 부분만 FastAPI TestClient로 변경.

## 변경한 부분과 이유

1. 표준 ThreadingHTTPServer를 FastAPI로 교체: 기존 API·CSRF·작업 큐는 유지하고 OpenAPI와 비동기 요청 처리를 제공.
2. `detection.py` 추가: 120클래스 best.pt 지연 로딩, 클래스 이름 검사, 좌표/신뢰도, 불확실 후보 분리. 모델을 받으면 연결 가능. YOLO 추론 시 사진 입력 최대 1280, 추론 크기 기본 640. 기존 VLM은 448 유지.
3. YOLO 경로는 이미지 결과 캐시를 건너뛰어 모델 추가·교체가 다음 촬영에 반영. 새 best.pt는 복사 완료 후 서버 재시작 권장.
4. `workflow.py` 추가: LLM 후보와 코드 근거 확정 분리. 상태를 변경할 수 있는 도구를 네 종류로 제한하고 인자 범위 검사.
5. MediaPipe IMAGE에서 VIDEO로 변경: 서버 생성 단조 증가 타임스탬프, 추적 사용. recognizer는 별도 잠금으로 LLM 작업과 분리.
6. UI에 명령 입력·JSON 로그·복합 입력 선택 추가. 직접 제스처와 복합 입력의 이중 실행 방지.
7. 분 설정 시퀀스와 신뢰도/연속성/시간 초과 검사 추가. 손가락 개수는 랜드마크 기하식이므로 실제 사용자별 조정 필요.
8. `--check`에 torch CUDA 커널 스모크와 llama GPU offload 진단 추가. CPU 빌드 여부를 GPU 사용 설정과 구별.
9. 모델별 추론 시간·로딩 시간·캐시 지표 제공. 작업 중 큰 모델 중복 로딩을 방지.

## 추가 작업이 필요한 부분

- 50 epoch 학습 완료 후 best.pt 복사, 실제 클래스 120개와 클래스명 검증.
- Windows RTX 5060 Ti에서 CUDA/llama.cpp 빌드와 VRAM 사용 확인. 제공 코드는 설치 성공을 보장하는 바이너리 묶음이 아니다.
- 실제 웹캠 조명·가림·배경·다중 재료에 대한 오탐/미탐 평가. validation/test mAP와 웹캠 현장 평가를 별도 보고.
- Qwen 한국어/JSON 출력 품질, 첫 호출·반복 호출 시간 측정.
- 실제 손 인식률·오동작률, 손가락 시퀀스의 3/4/5개 판정, 얼굴·양손 혼입 확인.
- 온디바이스 보드 이식, 모델 양자화/하드웨어 가속 최적화, 음성 기반 F306 전송, 연속 복수 도구 실행은 미구현.
