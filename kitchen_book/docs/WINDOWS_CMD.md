# Windows CMD 설치·실행

## 1. 기존 환경을 유지하는 방법

현재 YOLO 학습이 진행 중이면 해당 CMD와 가상환경을 그대로 둔다. 학습 중인 패키지를 업그레이드하지 않는다. 별도 폴더·가상환경에서 DEMO를 확인하거나 학습 종료 후 기존 프로젝트에 새 source를 적용한다.

기존 모델과 llama-cpp-python, MediaPipe가 정상 작동하던 가상환경에서는:

```cmd
cd /d C:\Users\SSAFY\Downloads\kitchen_book
.venv\Scripts\activate
python -m pip install -r source\requirements-workflow.txt
python source\app.py --check
python source\app.py
```

가상환경 이름이 `.venv`가 아니라 `venv`였다면 `venv\Scripts\activate`를 사용한다. `where python`과 `python -m pip --version`으로 같은 환경인지 확인한다. `requirements-workflow.txt`는 FastAPI, Uvicorn, Ultralytics만 추가한다. 기존에 성공한 llama 설치를 CPU 버전으로 덮어쓰지 않는다.

## 2. 새 환경에서 시작

Python 3.12 / 64비트 기준. Python 자체의 가상환경이며 가상 머신이나 Docker는 필요하지 않다.

```cmd
cd /d C:\Users\SSAFY\Downloads\kitchen_book
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r source\requirements.txt
```

이후 llama-cpp-python을 별도로 설치해야 실제 Qwen을 사용할 수 있다. 첨부 원본의 버전 기준은 0.3.34이다. 기존에 성공한 설치 방법을 우선 사용한다. CPU wheel이 해당 Python/Windows에 제공되는 경우에만 다음 명령이 성공한다.

```cmd
python -m pip install -r source\requirements-llm-cpu.txt
```

호환 wheel이 없으면 설치가 실패하며, 자동으로 수십 분짜리 소스 빌드로 전환하지 않도록 binary-only로 설정했다. 이 환경에서는 Windows wheel 제공 및 설치 성공을 확인하지 못했다. `No matching distribution`은 프로젝트 소스 오류가 아니다. 모델 없는 UI 확인은 `requirements-demo.txt`만 설치해 `--demo`로 실행할 수 있다.

## 3. 모델 배치

| 경로 | 용도 |
|---|---|
| `models\best.pt` | FOOD-INGREDIENTS 120클래스로 학습한 YOLO11n |
| `models\Qwen3-4B-Q4_K_M.gguf` | 메뉴·레시피·의도 선택 |
| `models\Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` | best.pt 없을 때 기존 사진 인식 |
| `models\mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf` | 위 VLM과 맞는 projector |
| `models\gesture_recognizer.task` | MediaPipe 제스처 |
| `models\ingredient_labels_ko.json` | 선택적 영문 이름→한국어 이름 매핑 |

기존 모델 위치를 그대로 쓸 수도 있다.

```cmd
set "KITCHEN_MODELS=C:\Users\SSAFY\Downloads\kitchen_book\models"
set "KITCHEN_YOLO=best.pt"
set "KITCHEN_LLM=Qwen3-4B-Q4_K_M.gguf"
python source\app.py --check
```

`KITCHEN_YOLO`에 완전한 파일 경로를 지정해도 된다. 다만 학습 저장 중인 weights를 연결하는 대신 완료한 파일을 models로 복사하는 편이 명확하다.

## 4. RTX 5060 Ti GPU

YOLO의 PyTorch CUDA와 LLM의 llama.cpp CUDA는 서로 별도이다. PyTorch에서 GPU가 보여도 llama-cpp-python이 CPU 빌드일 수 있다. 먼저 진단한다.

```cmd
nvidia-smi
python source\app.py --check
```

진단 결과 `torch.kernel_smoke_pass: true`이면 작은 CUDA 연산이 실제 실행된 것이다. `llama_cpp.gpu_offload: true`는 GPU offload를 지원하는 빌드라는 뜻이며 실제 모델 로딩·VRAM 여유까지 증명하지는 않는다.

둘 다 준비된 환경에서:

```cmd
set "KITCHEN_YOLO_DEVICE=0"
set "KITCHEN_GPU_LAYERS=-1"
set "KITCHEN_DETECTOR=auto"
python source\app.py
```

GPU 기본값은 안전한 CPU 설정이다. 위 환경변수를 넣어야 GPU를 사용한다. CPU로 실행했는데 GPU 속도를 기대하지 않도록 화면 health에도 현재 설정을 제공한다. VRAM 부족 시 GPU layers를 20 등으로 낮추거나 YOLO를 CPU로 돌린다. 실제 최적값은 GPU 메모리 용량과 모델을 보고 측정해야 한다.

새 환경에서 PyTorch CUDA가 필요하면 공식 설치 선택기에서 Windows/Pip/Python/호환 CUDA를 확인한다. CUDA 12.8 배포를 설치하는 예시는 다음과 같다. 이미 학습이 GPU에서 잘 돌아가는 환경에는 재설치하지 않는다.

```cmd
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

공식 문서는 Blackwell 지원과 CUDA 12.8 배포를 설명한다. Windows 및 현재 버전에 맞는 명령은 공식 선택기를 우선한다. 이 명령의 RTX 5060 Ti 현장 설치 성공은 미검증이다.

llama-cpp-python CUDA 소스 빌드가 필요한 경우에는 Visual Studio C++ Build Tools와 해당 GPU를 지원하는 CUDA Toolkit을 먼저 준비하고 **x64 Native Tools Command Prompt**에서 빌드한다. 일반 CMD에 C++ 컴파일러가 없는 상태에서는 CMake 오류가 날 수 있다. 기존 성공 설치를 보존하는 것이 우선이다. CUDA 12.8 이상과 sm_120을 대상으로 구성하는 예:

```cmd
.venv\Scripts\activate
set "CMAKE_ARGS=-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120"
python -m pip install --force-reinstall --no-cache-dir --no-binary llama-cpp-python "llama-cpp-python==0.3.34"
set "CMAKE_ARGS="
python source\app.py --check
```

이 빌드 명령은 이 환경에서 실행·성공 확인하지 못했다. 툴킷, 드라이버, 패키지 버전의 호환성은 사용자 PC에서 확인해야 한다. 비공식 wheel 링크를 임의로 제공하지 않았다.

## 5. 실행과 종료

```cmd
python source\app.py
```

Chrome/Edge에서 http://127.0.0.1:8000 접속 → 웹캠 허용. 서버 종료는 실행 CMD에서 Ctrl+C. 포트 충돌 시:

```cmd
python source\app.py --port 8001
```

이 경우 http://127.0.0.1:8001 로 접속한다. IDE는 실행과 별개이므로 VS Code 터미널을 CMD 프로필로 열어 같은 명령을 써도 된다.

## 6. 검증과 실측

서버 실행 상태에서 새 CMD를 연다. 같은 프로젝트 루트로 이동 후 가상환경 활성화.

```cmd
python -m pip install -r source\requirements-test.txt
python -m unittest discover -s source\tests -p "test*.py"
node source\tests\test_core.cjs
python scripts\verify_api.py --mode demo --output docs\api_validation_demo.json
```

마지막 명령의 서버는 `--demo`로 실행 중이어야 한다. 실제 모델 서버는 `--mode live`를 사용한다. 다른 포트는 `--url http://127.0.0.1:8001`.

브라우저 카메라를 잠시 끄고 실사진을 저장하려면:

```cmd
python scripts\capture_webcam.py --output webcam.jpg
```

창에서 Space 저장 / Q 취소. 저장한 뒤:

```cmd
python scripts\verify_api.py --mode live --image webcam.jpg --ingredients "달걀,토마토,양파" --output docs\api_validation_live.json --require-all
python scripts\evaluate_detector.py --data training\dataset\data.yaml --model models\best.pt --device 0 --split test --output docs\detector_metrics.json
```

test split이 실제로 없으면 데이터 정의를 확인하고 `--split val`로 바꾸되 결과를 test 점수라고 부르지 않는다. 누락 파일이 있는 데이터셋에서는 먼저 경로/라벨 쌍을 확인한다. 자동 API 검증은 실제 모델 응답과 규칙을 확인하며, 실물 정확도는 `PHYSICAL_WORKFLOW_CHECKLIST.md`에 별도 기록한다.

## 7. 설정·오류 해결

| 증상 | 확인 |
|---|---|
| 1.2.0 화면/다른 source 실행 | 이전 서버 종료, `cd` 위치 확인, `python source\app.py`, Ctrl+F5 |
| `No module named fastapi` | 활성화 환경에서 `python -m pip install -r source\requirements-workflow.txt` |
| `No module named llama_cpp` | 같은 가상환경에 실제 LLM 런타임 설치. DEMO만으로 설치 완료 판정하지 않음 |
| best.pt 없음 | auto는 VLM, yolo는 오류. `models`와 `source`가 형제인지 확인 |
| 모델이 120클래스가 아님 | 일반 COCO yolo11n.pt가 아닌 학습 결과 best.pt 사용 |
| 클래스명이 영문 | 정상 처리. 실제 이름을 `export_class_names.py`로 확인한 뒤 alias JSON에 정확히 매핑 |
| 사진 인식 후보가 적음 | 조명·거리·가림·촬영 범위를 조정. threshold 조정은 검증 데이터로 결정 |
| 낮은 신뢰도 후보가 목록에 없음 | uncertain에 분리됨. 직접 확인 후 재료 입력에 추가 |
| 제스처 이름만 나오고 실행 안 됨 | 점수/연속 0.9초 유지 확인, 손동작 함께 사용 체크 여부 확인, 현재 책/타이머 모드 확인 |
| 분 시퀀스 취소 | 🤟로 시작 후 5초 안에 개수 유지+손 내리기. 실제 카메라 성능에 따라 튜닝 필요 |
| AI 작업이 오래 걸림 | 첫 모델 로딩 포함 여부, CPU/GPU 설정, 작업 metrics 확인. 학습과 동시 GPU 사용 피하기 |
| JSON 생성 실패 | `set "KITCHEN_AI_ATTEMPTS=2"`로 최대 1회 추가 재시도 가능. 시간이 늘어남 |
| 409 AI 작업 중 | 단일 작업 완료까지 기다림. 중복 모델 호출 방지 설계 |

기본 설정: YOLO size 640 / conf .25 / accept .50 / IoU .50, VLM 이미지 448, context 4096, 최대 CPU thread 6. 환경변수는 현재 CMD와 그 자식 프로세스에만 적용되며 서버 재시작 시 읽는다.

## 공식 기술 근거

- Ultralytics 예측 API·boxes·device: https://docs.ultralytics.com/modes/predict/
- MediaPipe VIDEO·timestamp API: https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer/python
- llama-cpp-python 빌드·CUDA: https://github.com/abetlen/llama-cpp-python
- PyTorch 설치 선택기: https://pytorch.org/get-started/locally/
- Blackwell / CUDA 12.8 소개: https://pytorch.org/blog/pytorch-2-7/

문서 확인일 2026-10-23. 외부 라이브러리 설치·모델 실행은 현장 검증 항목이며 본 코드 테스트 결과와 구별한다.
