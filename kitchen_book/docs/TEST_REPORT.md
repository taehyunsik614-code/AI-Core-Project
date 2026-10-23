# 테스트 결과 및 남은 문제

검증일: 2026-10-23 / 대상: kitchen_book 1.3.0

## 결론

코드·규칙·DEMO HTTP·DOM Workflow는 실행 검증했다. **실제 웹캠부터 YOLO/Qwen/MediaPipe를 거치는 전체 Workflow는 이 환경에서 검증하지 못했다.** best.pt 및 GGUF·gesture 모델, Windows PC와 RTX 5060 Ti, 물리 카메라가 제공되지 않았기 때문이다. 기능 코드가 있는 것과 실제 장치에서 성능이 검증된 것을 구분한다.

## 실제 실행 결과

| 검증 | 결과 | 증거 / 범위 |
|---|---|---|
| Python unittest | 48개 PASS | `python_tests.log`. 기존 27개 회귀 + 규칙·YOLO 어댑터·MediaPipe VIDEO 호출 계약 |
| JavaScript 상태 머신 | 8개 PASS | `js_tests.log`. 타이머, 복원, 중복 제스처 방지, 유지 끊김, 시퀀스 |
| 서버 API 자동 검증 | 24 PASS / 0 FAIL / 1 SKIP | `api_validation_demo.json`. DEMO 서버, A1/A3/A4/A5·규칙·충돌 |
| A2 실제 제스처 API | SKIP | 실제 MediaPipe 모델 부재. fake adapter 호출 계약은 Python에서 별도 통과 |
| DOM 통합 | PASS | `integration.log`. jsdom + 실제 FastAPI 서버, 카메라·손 응답만 가짜 입력 |
| Python/JS 문법 검사 | PASS | compileall, node --check |
| 실제 브라우저 렌더링·반응형 Playwright | 미실행 | Chromium 없음. 다운로드 시 아카이브 오류로 설치 실패. 기존 UI/레이아웃 테스트 파일 보존 |
| Windows CMD 설치, CUDA·VRAM | 미검증 | Linux Python 환경에서 테스트. Windows 가이드와 GPU 진단 코드 제공 |
| Qwen 실제 추론·한국어·출력 품질 | 미검증 | 모델과 llama_cpp 없음. Fake model의 schema/검증 흐름만 확인 |
| YOLO best.pt 정확도·mAP·속도 | 미측정 | 학습 진행 중이며 best.pt/평가 데이터 미제공 |
| 실제 손 제스처 성공률·오동작률 | 미측정 | 실기기 검증표 제공 |

환경: Python 3.12, FastAPI 0.161.1, Uvicorn 0.54.0, httpx 0.28.1. 테스트 중 나타나는 `Invalid ... response`와 `AI job failed ... 모델 오류`는 잘못된 출력/오류 복구를 일부러 발생시킨 회귀 테스트의 예상 로그이다. unittest 최종 결과는 OK이다. Starlette의 httpx 사용 deprecation 경고가 있으나 테스트 실패는 아니다.

## DOM에서 실제로 확인한 동작

- 가짜 웹캠 JPEG 캡처 → HTTP ingredients 작업 → 확인 체크 → 메뉴 3개 → 레시피 생성.
- 4단계 전환, 뒤로 가기, 카메라 영역 이동, 재료 수정 시 확인 취소, 메뉴 재선택.
- 실제 poll → GestureGate → dispatcher → UI로 7개 기본 포즈 처리.
- 단계 시간 보정, 주먹으로 단계 시간 로딩, 시간 없는 단계 직접 조절.
- 타이머 시작·일시정지·초기화, 종료 알림, 새로고침 데이터 복원, 페이지 이동 중 실행 유지.
- 명령 입력 → FastAPI 작업 → 도구 응답 → 실제 타이머·페이지 변경.
- “타이머 설정” → “3분” 되묻기 연결.
- 텍스트와 손 근거 충돌 시 텍스트 우선, 손만 방향 근거인 경우 처리.
- 🤟 → 손가락 2개 → 손 내리기 응답 시퀀스로 실제 타이머 2분 설정.

이 결과는 물리 카메라나 모델의 인식 능력, 글꼴/배치가 실제 브라우저에서 잘 보이는지까지 검증한 결과가 아니다.

## 남은 문제와 제한

1. 가중치를 받지 못했으므로 120개 클래스 전체 번역·클래스별 정확도를 확정할 수 없다. 코드가 best.pt names를 읽고 이름 매핑이 없는 항목은 영문으로 유지한다. 제공 한국어 매핑은 일부 재료만 포함한다.
2. 실제 Qwen 구조화 출력이 토큰 한도에서 잘 완성되는지 확인해야 한다. JSON 검증 실패는 감추지 않고 표시한다. `KITCHEN_AI_ATTEMPTS=2`로 한 번 더 시도할 수 있으나 더 느려질 수 있다.
3. GPU 설정은 YOLO와 llama.cpp가 별도다. 기본 CPU이며 지원 빌드/드라이버 확인 후 설정해야 한다. 실제 속도 개선량이나 GPU 동시 상주 메모리를 측정하지 않았다.
4. 손가락 개수는 랜드마크 각도·거리 기준의 기하식이다. 손 크기·각도·조명·장갑 등에 따른 오차를 실물 검증해야 한다. 복합 명령은 안정된 손 스냅샷이 없으면 질문한다.
5. 한 번에 한 명령을 처리한다. 복수 동작 문장, 모든 한국어 부정문·동의어·장거리 대화를 완벽히 해석하는 기능은 아니다. 짧은 명령과 직전 되묻기 문맥을 지원한다.
6. F306은 텍스트 입력 + 손이다. 2단계 기존 브라우저 음성 입력은 유지했지만, 레시피북 명령창 음성 전송은 미구현이다. 브라우저 음성 기능은 네트워크 서비스를 사용할 수 있다.
7. 알람은 브라우저를 열어 둔 상태의 기능이다. 탭 종료·절전·기기 종료 시 알람을 보장하지 않는다.
8. 단일 PC·단일 사용자 로컬 서버다. 여러 브라우저 탭이 서로 다른 손 영상 스트림을 같은 VIDEO recognizer에 섞어 보내는 사용은 대상이 아니다. 온디바이스 보드 이식도 완료하지 않았다.
9. 로컬 UI는 CDN 없이 동작한다. FastAPI `/docs` 보조 문서는 기본 Swagger UI CDN을 사용하므로 완전 오프라인에서는 `/openapi.json`과 이 문서를 이용한다.

## 재현 및 다음 검증

프로젝트 루트에서:

```cmd
python -m pip install -r source\requirements-test.txt
python scripts\run_checks.py
npm install --no-save jsdom
python scripts\run_checks.py --dom
```

Node.js가 필요하다. 실모델 서버에서는 `verify_api.py --mode live --image 실제사진.jpg --require-all`을 실행한다. `--require-all`은 SKIP도 종료코드 2로 반환하며 FAIL은 1이다. `evaluate_detector.py`로 독립 데이터셋 성능을 측정하고 `PHYSICAL_WORKFLOW_CHECKLIST.md`를 완료해야 실기기 Workflow 검증 완료라고 할 수 있다.

DEMO의 `elapsed_seconds: 0.0`은 고정 예시가 매우 빨리 반환된 결과이며 실제 모델 추론 속도가 아니다.
