# kitchen_book 1.3.0 · 비접촉 AI 레시피북

**Pi 마이크 업데이트** · 설치와 단계별 음성 명령은 [Pi 음성 실행 안내](docs/PI_VOICE.md)를 확인하세요.

웹캠 식재료 인식 → 재료 확인·수정 → 메뉴 추천 → 레시피북 → 손 제스처 페이지·타이머 제어.

첨부된 기존 1.2.0 소스를 분석해 수정했다. 로봇·격자 시뮬레이터는 포함하지 않는다. F301~F306의 학습 구조를 레시피북 도구 호출로 적용했다. **학습 가중치는 포함하지 않는다. 실제 웹캠·Qwen·RTX 5060 Ti 결과는 아직 검증되지 않았고, 코드/규칙/DEMO 흐름만 검증했다.** 자세한 범위는 `docs/TEST_REPORT.md`에 있다.

## 먼저 확인할 파일

| 경로 | 내용 |
|---|---|
| `source/` | 실행 소스·정적 UI·테스트. `python source\app.py` |
| `models/` | 기존 모델과 학습 후 best.pt를 넣는 곳. 일부 한국어 표시명 매핑 포함 |
| `docs/API_DESIGN.md` | A1~A5, R1~R5, 요청/응답 및 도구 |
| `docs/IMPLEMENTATION_F301_F306.md` | 요구사항별 코드·검증·미검증 구분 |
| `docs/WINDOWS_CMD.md` | 설치·GPU 설정·실행·best.pt 연결·문제 해결 |
| `docs/TEST_REPORT.md` | 실제 수행한 테스트와 남은 문제 |
| `docs/PHYSICAL_WORKFLOW_CHECKLIST.md` | Windows 실기기 검증·시연 순서 |
| `scripts/verify_api.py` | 실행 중 서버를 검사하고 PASS/FAIL/SKIP 출력 |
| `scripts/run_checks.py` | 단위 + 자동 데모 서버 API 테스트, 선택적 DOM 테스트 |
| `scripts/evaluate_detector.py` | 사용자의 데이터셋에서 mAP/속도 측정 |
| `scripts/capture_webcam.py` | 실제 웹캠 JPEG 저장 |

## 기존 프로젝트에 적용

압축에는 `kitchen_book` 폴더가 한 번만 들어 있다. 그 안에서 **source와 models가 같은 위치**에 있어야 한다. 기존 `source`를 백업한 뒤 이 ZIP의 `source`로 교체하고 `docs`, `scripts`를 같은 위치에 복사한다. 기존 models와 학습 중인 training 폴더는 보존한다. `models/ingredient_labels_ko.json`만 선택적으로 추가한다. `source` 안에 또 `source`를 넣지 않는다.

학습 중인 환경을 변경하지 않으려면 별도 폴더에 압축을 풀어 DEMO를 먼저 확인한다. 기존 가상환경과 모델이 정상인 경우 다음이 가장 짧은 실행 순서다. 아래 경로는 실제 프로젝트 위치로 바꾼다.

```cmd
cd /d C:\Users\SSAFY\Downloads\kitchen_book
.venv\Scripts\activate
python -m pip install -r source\requirements-workflow.txt
python source\app.py
```

브라우저: http://127.0.0.1:8000 . 1.3.0이 안 보이면 실행 중인 이전 서버를 Ctrl+C로 종료하고 새 서버 실행 후 Ctrl+F5로 새로고침한다.

## best.pt가 아직 없는 동안

기본 `auto` 모드는 기존 Qwen2.5-VL-3B와 projector로 식재료를 인식한다. 이 파일도 없으면 재료 직접 입력 → 메뉴 추천부터 진행할 수 있다. Qwen3-4B가 없으면 메뉴·레시피·AI 명령은 실제 생성할 수 없다. 전체 화면/규칙만 확인하려면:

```cmd
python -m pip install -r source\requirements-demo.txt
python source\app.py --demo
```

DEMO는 사진과 무관한 고정 식재료·메뉴·레시피이며, 명령은 규칙 테스트다. 실제 제스처는 DEMO에서도 MediaPipe와 gesture 모델이 필요하다.

## 학습 완료 후 연결

프로젝트 루트에서, 현재 학습 경로가 아래와 같다면:

```cmd
copy training\runs\ingredients_120\weights\best.pt models\best.pt
python scripts\export_class_names.py
set "KITCHEN_DETECTOR=yolo"
set "KITCHEN_YOLO_DEVICE=0"
python source\app.py --check
python source\app.py
```

자동으로 ingredients_120, ingredients_1202처럼 이름이 달라졌다면 실제 폴더를 사용한다. 학습 프로세스가 저장 중인 파일을 직접 읽지 말고 학습 완료본을 복사한다. `--check`가 GPU 실패를 보고하면 아래 CPU 설정으로 우선 기능을 확인한다. 모델 파일명·경로 변경은 `docs/WINDOWS_CMD.md` 참고.

```cmd
set "KITCHEN_YOLO_DEVICE=cpu"
set "KITCHEN_GPU_LAYERS=0"
python source\app.py
```

## 기본 손동작

각 포즈를 약 0.9초 유지한다. 같은 동작을 다시 실행하려면 손을 잠시 내려 준다. 책 모드와 타이머 모드를 화면에서 확인한다.

| 포즈 | 책 모드 | 타이머 모드 |
|---|---|---|
| 👍 | 다음 페이지 | 시작·재개 |
| 👎 | 이전 페이지 | 일시정지 |
| ✌️ | 타이머 모드 열기 | 책 모드로 돌아가기 |
| ✊ | 현재 단계 시간 설정, 타이머 모드 진입 | 설정값으로 초기화 |
| ☝️ | 없음 | 시간 증가 |
| 🖐 | 없음 | 시간 감소 |
| 🤟 | 분 설정 시퀀스 시작 | 조절 단위 변경 |

분 설정 시퀀스: 책 모드에서 🤟 → 손가락 1~5개를 유지 → 손 내리기. 5초 안에 완료하면 1~5분을 설정하며 자동으로 시작하지 않는다. 👍로 시작한다. 기본 조절 단위는 1분이며 5분 → 1초 → 10초 → 1분 순으로 바꿀 수 있다. 기존의 임의 시간 조절도 유지된다.

## AI 명령

레시피북 화면에서 “다음 2페이지”, “타이머 3분 설정”, “타이머 시작”, “타이머 일시정지”, “타이머 초기화”를 입력한다. “타이머 설정”이라고만 하면 시간을 되묻고 “3분”으로 이어 답할 수 있다.

“손동작 함께 사용”을 체크하면 직접 제스처 실행은 중단된다. 제스처 인식을 켠 상태에서 손을 안정적으로 유지하고 “이쪽으로 2페이지”를 전송한다. 명시한 텍스트가 손동작과 충돌하면 텍스트를 우선한다. 음성을 통한 이 명령 전송은 추가하지 않았다.

## 검증 실행

```cmd
python -m pip install -r source\requirements-test.txt
python -m unittest discover -s source\tests -p "test*.py"
node source\tests\test_core.cjs
python scripts\run_checks.py
```

`run_checks.py`는 Node.js가 필요하며 8765 포트를 사용하는 임시 DEMO 서버를 생성하고 종료한다. DOM 검증은 프로젝트 루트에서 `npm install --no-save jsdom` 후 `python scripts\run_checks.py --dom`.

실제 서버를 켠 상태에서 별도 CMD:

```cmd
.venv\Scripts\activate
python scripts\verify_api.py --mode live --image webcam.jpg --ingredients "달걀,토마토,양파" --output docs\api_validation_live.json --require-all
```

`webcam.jpg`는 실제 사진이다. `--ingredients`에는 사진과 대조해 확인한 실제 재료를 입력한다. API 스모크 성공만으로 실제 인식 정확도·손동작 정확도가 검증되지는 않는다. 실기기 검증표를 별도로 완료한다.
