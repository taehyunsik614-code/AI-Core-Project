#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo 'OLED와 카메라가 작동한 Pi 가상환경을 활성화하고 다시 실행하세요.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y alsa-utils cmake build-essential git curl libopenblas-dev python3-dev
if [[ ! -d "$HOME/whisper.cpp" ]]; then
  git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$HOME/whisper.cpp"
fi
cmake -S "$HOME/whisper.cpp" -B "$HOME/whisper.cpp/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$HOME/whisper.cpp/build" --target whisper-cli -j2
if [[ ! -s "$HOME/whisper.cpp/models/ggml-base.bin" ]]; then
  (cd "$HOME/whisper.cpp" && bash models/download-ggml-model.sh base)
fi
CMAKE_BUILD_PARALLEL_LEVEL=2 CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" python -m pip install 'llama-cpp-python>=0.3.9,<0.4'
mkdir -p "$root/models"
model="$root/models/Qwen3-1.7B-Q4_K_M.gguf"
if [[ ! -s "$model" ]]; then
  curl --fail --location --retry 3 -o "$model.part" https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf
  mv "$model.part" "$model"
fi
arecord -l
