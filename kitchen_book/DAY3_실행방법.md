# 3일차 · 대화형 주방 레시피북

어제 사용한 라즈베리파이 5, 같은 SD 카드, 카메라·마이크·버튼·OLED·LED를 사용한다. Windows가 사진 인식·레시피 생성과 웹을 담당하고 Pi가 Whisper 한국어 인식과 Qwen3-1.7B 도구 선택을 담당한다. 기기 입력란에 타이핑한 질문과 버튼으로 말한 질문은 같은 판단 경로를 사용한다.

## 1. 집 Windows 컴퓨터 · 최초 한 번

ZIP을 C:\KitchenDay3에 풀어 C:\KitchenDay3\kitchen_book\source\app.py가 있는지 확인한다. 아래 명령은 Windows CMD에서 실행한다. 설치와 모델 다운로드에는 인터넷이 필요하다.

~~~bat
cd /d C:\KitchenDay3\kitchen_book
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r source\requirements.txt
scripts\get_pc_models.cmd
~~~

같은 PC에서 이미 정상 작동했던 환경을 사용한다면 기존 가상환경과 모델을 사용할 수 있다. 다운로드 스크립트는 models 안에 같은 이름의 파일이 있으면 건너뛴다. 사진·레시피 모델 3개와 손동작 모델을 받는다. 예제 레시피로 기기 음성만 시험할 때는 PC 대형 모델 다운로드를 나중에 마쳐도 된다.

## 2. 집 네트워크와 Pi 전송

Pi와 PC를 같은 집 네트워크에 연결한다. Pi 터미널에서 hostname -I로 IPv4 주소를 확인한다. 아래는 예시이므로 실제 주소로 변경한다. Windows CMD에서 실행한다.

~~~bat
cd /d C:\KitchenDay3\kitchen_book
set "PI_IP=192.168.0.25"
scripts\install_day3_device.cmd pi@%PI_IP%
ssh pi@%PI_IP%
~~~

Pi 비밀번호를 입력한다. pi@raspberrypi 프롬프트가 뜨면 Pi에 접속한 상태다.

## 3. Pi 모델 최초 설치와 서버 실행

~~~bash
cd ~/kitchen_book
bash scripts/setup_day3_pi.sh
/home/pi/venv/bin/python raspberrypi/camera_server.py --voice --alsa plughw:0,0
~~~

설치 스크립트는 기존 Whisper를 확인하고, 기기 추론 패키지와 Qwen3-1.7B-Q4_K_M.gguf를 준비한다. 컴파일러가 없다는 오류가 나오면 Pi에서 sudo apt install build-essential python3-dev cmake 실행 후 재시도한다. 설치가 끝나면 다음부터는 마지막 서버 실행 명령만 쓴다. 마이크 카드 번호가 바뀌면 arecord -l에서 확인한다.

Pi에서 모델 저장소 접속이 시간 초과되면 Windows CMD에서 다음처럼 모델을 받아 복사한다. 패키지 설치까지 실패했다면 Pi 인터넷 연결 또는 Pi의 파이썬 버전에 맞는 ARM64 패키지도 준비해야 한다.

~~~bat
curl.exe -fL --retry 2 -o Qwen3-1.7B-Q4_K_M.gguf https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf
scp Qwen3-1.7B-Q4_K_M.gguf pi@%PI_IP%:~/kitchen_book/models/
~~~

## 4. Windows 서버 실행

Pi 창은 켜 둔다. 새 Windows CMD에서 집 주소를 다시 지정한다.

~~~bat
cd /d C:\KitchenDay3\kitchen_book
set "PI_IP=192.168.0.25"
source\run_windows.bat --device %PI_IP%
~~~

http://127.0.0.1:8000 을 연다. 이미 열린 페이지는 Ctrl+F5로 새로고침한다. 종료할 때는 두 서버 창에서 각각 Ctrl+C를 누른다.

## 5. 주방 시연 순서

1. **레시피 불러오기**에서 examples\kitchen-demo.json을 선택한다. 1/4에서 시작한다.
2. **주방 레시피** 모드에서 “다음 단계”를 타이핑해 2/4로 이동한다. 첫 요청은 모델 로딩을 기다린다.
3. Pi 버튼을 누른 채 “지금 뭐 하면 돼?”라고 말하고 뗀다. 페이지는 2/4에 머물고 현재 오이 썰기 지시가 웹에 표시된다.
4. “두 단계 이동해 줘”를 입력한다. 되묻기 중에는 페이지가 바뀌지 않는다.
5. 버튼으로 “다음으로”라고 답한다. 4/4로 이동하고 OLED도 갱신되는지 확인한다. 방향을 제안받았으면 “응”도 사용할 수 있다.
6. “얼마나 기다려?”라고 묻는다. 예제의 4단계는 1분이다. 2단계에서는 지정된 시간이 없다고 표시한다.
7. 기기 모델에 되묻기를 받은 후 Pi 서버를 Ctrl+C로 종료한다. 기기 연결이 끊겨도 PC 레시피와 수동 버튼은 동작한다. Pi 서버를 다시 시작하고 같은 탭·페이지에서 후속 답을 전송한다. 새로고침하면 대화 기록은 초기화된다.

## 6. 명세서 방향 시연

- **방향 검증 · 컴퓨터**에서 “오른쪽으로 3칸 가”를 입력한다. PC 모델이 판단하고 칸 수를 안내한다.
- **방향 검증 · 기기**에서 같은 문장을 타이핑하거나 말한다. 화면은 방향만 안내하고 OLED에 RIGHT, GPIO17에 점멸이 나타나는지 확인한다.
- “오른쪽 두 칸 가고 위로 한 칸”은 OLED RIGHT, UP 순서이며 우측 LED만 세 번 점멸한다. “왼쪽”은 GPIO27, “아래로”는 OLED만 사용한다.
- “저쪽으로 두 칸 가” → 되묻기 → “왼쪽” 또는 제안에 “응”. 최초 입력의 칸 수는 구조화된 응답에 유지된다.
- 장면을 물으려면 카메라를 먼저 켜고 “앞에 뭐가 보여?”를 입력한다. 현재 프레임에서 PC 시각 모델이 만든 설명을 사용한다.
- 응답이 지연되면 처리 중 표시를 확인한다. 시간 초과 시 같은 탭에서 같은 후속 답을 다시 보낼 수 있다.

## 7. 통합 검증

Windows 서버를 켜 둔 상태로 세 번째 CMD에서 실행한다. 아래 주소는 집 주소로 바꾼다.

~~~bat
cd /d C:\KitchenDay3\kitchen_book
.venv\Scripts\python scripts\verify_day3.py --quick
.venv\Scripts\python scripts\verify_day3.py
.venv\Scripts\python scripts\verify_day3.py --device 192.168.0.25
~~~

빠른 검사는 모델·기기 없이 대시보드, 잘못된 입력, 연결 실패 응답을 검사한다. 기본 검사는 PC의 실제 모델과 인식 자산을 호출한다. 기기 검사는 D1~D5와 텍스트·음성 출처, LED·OLED 요청, 되묻기, 로컬 장애 격리를 추가한다. --image "사진경로.jpg"로 실제 주방 사진을 지정할 수 있다. 기기 검사의 음성 출처 요청은 인식 후의 문장을 사용하므로 물리 버튼과 실제 발화는 5절에서 관찰한다.

**원본 명세 A2와 A3까지 검사할 때** 브라우저 손동작 자산과 물체 인식 모델을 추가한다. npm이 설치된 Windows CMD에서 실행한다. 이미 확보한 yolo11n.pt는 models 폴더에 복사해도 된다.

~~~bat
npm install --no-save --package-lock=false @mediapipe/tasks-vision@0.10.22-rc.20250304
.venv\Scripts\python -m pip install ultralytics
curl.exe -fL -o models\yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
~~~

| 범위 | 확인 기준 |
|---|---|
| A1~A4 | 대시보드, 손동작 자산, 물체 인식, 장면 설명 |
| A5~A9 | 공통 도구 응답, 영상 중계, 방향 LED·OLED, 음성 결과 |
| D1~D5 | Pi 영상·LED·OLED·발화·모델 추론 |
| R1~R5 | 도구 형식, 이동 수 제한, 방향 근거, 되묻기 표시, 후속 답 |
| R6~R10 | 장애 격리, 탭 대화 기록, 방향 출력 순서, 공통 응답, 기기와 PC 문구 차이 |

개발 환경에서는 모의 대화, 웹 제어 회귀 검사, PC 서버 빠른 검사를 수행했다. 실제 Pi의 첫 추론 시간, 인식 정확도, 물리 LED·OLED, 실제 단절·재연결은 장비로 확인 후 README에 기록한다.
