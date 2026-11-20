#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python=/home/pi/venv/bin/python
"$python" -c "import gpiozero, picamera2, luma.oled"
test -x "$HOME/whisper.cpp/build/bin/whisper-cli"
test -s "$HOME/whisper.cpp/models/ggml-base.bin"
if ! "$python" -c 'from llama_cpp import Llama' 2>/dev/null; then
    export PATH="/home/pi/venv/bin:$PATH"
    CMAKE_BUILD_PARALLEL_LEVEL=2 "$python" -m pip install 'llama-cpp-python==0.3.34'
fi
mkdir -p models
name=Qwen3-1.7B-Q4_K_M.gguf
if [[ ! -s "models/$name" ]]; then
    curl -fL --retry 2 --connect-timeout 12 -C - -o "models/$name.part" "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/$name"
    mv "models/$name.part" "models/$name"
fi
echo '준비 완료. 마이크 카드 번호를 확인하세요.'
arecord -l
