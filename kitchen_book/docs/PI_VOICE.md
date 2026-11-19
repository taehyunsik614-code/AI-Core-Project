# Pi 마이크로 레시피북 조작하기

기존 PC 모델 세 개는 그대로 kitchen_book/models에 둡니다. 이 업데이트는 실제 SPH0645 마이크와 GPIO 버튼을 쓰며 웹 브라우저 마이크 권한은 필요하지 않습니다. 새 음성 기능은 --voice 옵션으로 켭니다. 먼저 실행 중인 PC와 Pi 서버의 터미널에서 Ctrl+C를 누르세요.

## 1. PC에서 소스 업데이트

압축을 별도 폴더에 풉니다. Windows CMD에서 압축을 푼 AI-Core-Project-master 폴더로 이동한 후 아래처럼 실행합니다. 첫 번째 인수는 모델 세 개와 기존 가상환경이 들어 있는 설치본의 kitchen_book 경로, 두 번째는 실제 Pi 로그인 주소입니다. 경로와 주소는 본인 값으로 바꾸세요.

```bat
UPDATE_WINDOWS.cmd "C:\내프로젝트\kitchen_book" pi@라즈베리파이IP
```

이 명령은 PC 소스와 웹 화면을 갱신하고 필요한 Pi 파일을 SSH로 ~/kitchen_book에 복사합니다. 기존 PC의 models와 가상환경은 그대로 사용합니다.

## 2. 전원을 끄고 마이크와 버튼 연결

| 부품 단자 | Pi 5 물리 핀 | 신호 |
|---|---:|---|
| SPH0645 3V | 1 | 3.3 V |
| GND, SEL | GND | 공통 접지, 왼쪽 채널 선택 |
| BCLK | 12 | GPIO18 |
| LRCL / WS | 35 | GPIO19 |
| DOUT | 38 | GPIO20 |
| 버튼 양쪽 접점 | 16과 14 | GPIO23과 GND, 내부 풀업 |

전원을 켠 뒤 Pi 터미널에서 `arecord -l`로 캡처 카드가 보이는지 확인합니다. 교안 구성의 카드 이름은 sndrpigooglevoi입니다. 이미 보이면 다음으로 진행합니다. 카드가 없고 교안과 같은 Google Voice HAT 호환 드라이버 구성을 쓴다면 /boot/firmware/config.txt의 [all] 아래에 다음 두 설정을 각각 한 번만 넣고 재부팅합니다. 기존 SPI/OLED 설정은 보존합니다.

```ini
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

## 3. Pi에 한국어 인식과 도구 선택 모델 설치

Windows CMD에서 SSH로 접속합니다.

```bat
ssh pi@라즈베리파이IP
```

Pi에서 기존 OLED 서버를 실행하던 가상환경을 활성화합니다. 아래의 첫 줄은 예시이므로 실제 가상환경 경로를 사용하세요. 인터넷이 연결된 상태에서 최초 한 번 설치합니다. 스크립트는 whisper.cpp를 빌드하고 한국어를 지원하는 ggml-base.bin 및 Qwen3-1.7B-Q4_K_M.gguf를 내려받습니다.

```bash
source ~/kitchen_book/.venv/bin/activate
cd ~/kitchen_book
bash raspberrypi/setup_voice.sh
arecord -l
```

예를 들어 캡처 카드가 1번이고 장치가 0번이면 다음과 같이 독립적으로 녹음하고 인식합니다. 카드 번호는 본인 장치에 맞추세요. 4초 동안 “다음 단계”라고 말합니다.

```bash
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 4 /tmp/kitchen-test.wav
~/whisper.cpp/build/bin/whisper-cli -m ~/whisper.cpp/models/ggml-base.bin -l ko -f /tmp/kitchen-test.wav
```

## 4. 두 서버 실행

Pi 터미널에서 위 테스트와 같은 ALSA 주소를 줍니다.

```bash
python raspberrypi/camera_server.py --voice --alsa plughw:1,0
```

다른 Windows CMD에서 기존 설치본의 source 폴더로 이동한 다음 실행합니다.

```bat
cd /d "C:\내프로젝트\kitchen_book\source"
run_windows.bat --device 라즈베리파이IP
```

브라우저로 http://127.0.0.1:8000 을 열고 Pi 명령 입력란이 보이는지 확인합니다. 입력란은 모든 단계에서 사용합니다. 버튼을 누르고 한 문장을 말한 뒤 뗍니다. 첫 명령은 Pi가 언어 모델을 메모리에 올리므로 시간이 더 걸립니다. 다음 발화는 현재 명령 결과가 표시된 뒤 시작하세요. 답은 웹의 글자로 표시됩니다.

## 단계별 확인

| 화면 | 말할 문장 | 확인할 결과 |
|---|---|---|
| 01 | 재료 찍어 줘 | Pi 카메라 자동 시작(이미 켜진 카메라는 그대로 사용), 촬영 후 02로 이동 |
| 02, 목록에 감자가 있을 때 | 감자가 아니라 양파야 | 감자가 양파로 교체되고 확인란이 해제됨 |
| 02 | 이 재료로 메뉴 추천해 줘 | 현재 목록을 확정하고 세 메뉴를 요청 |
| 03 | 두 번째 메뉴로 레시피 만들어 줘 | 선택한 메뉴로 생성한 뒤 04로 이동 |
| 04 | 다음 단계 / 이전 단계 | 웹과 OLED의 조리 단계 번호가 함께 바뀜 |
| 04 | 지금 뭐 해야 해? | 현재 레시피의 실제 조리 지시를 웹에 표시 |

빠르게 확인하려면 기존에 저장한 레시피를 불러오고 04에서 시작하세요. Pi 명령 입력란에 같은 문장을 타이핑하면 음성 인식을 건너뛰고 동일한 Pi 명령 해석 경로를 검사합니다. 인식된 원문은 입력란에 남으므로 잘못 들은 단어를 구분할 수 있습니다.

## 문제 구분

- 버튼 신호와 음성 결과는 Pi의 별도 터미널에서 `curl -s http://localhost:8080/voice-text | python -m json.tool --no-ensure-ascii`로 확인합니다. 누르는 동안 상태가 녹음 중으로 바뀌고 뗀 뒤 seq가 증가해야 합니다.
- text가 비어 있으면 위의 4초 녹음 테스트, 마이크 SEL과 카드 번호부터 확인합니다. 마이크가 열리지 않으면 별도의 녹음 프로그램을 종료합니다.
- 인식 문장은 맞는데 해석이 실패하면 Pi 터미널에서 모델 경로와 llama-cpp-python 설치 환경을 확인합니다. camera_server.py는 설치에 쓴 가상환경에서 실행합니다.
- 웹 페이지를 연 뒤 한 탭에서 시험합니다. 새로 연 화면에서는 직전 발화를 재실행하지 않습니다. 기기 서버만 재시작했다면 웹의 연결이 복구된 다음 새 명령을 말하세요.
- Pi 명령은 로컬 주방 네트워크에서 실행합니다. 조리 지시 음성 낭독이나 로봇 방향 시뮬레이터는 이 주방 명령 흐름의 범위에 포함되지 않습니다.
