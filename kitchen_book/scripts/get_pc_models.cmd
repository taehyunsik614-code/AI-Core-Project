@echo off
setlocal
cd /d "%~dp0.."
if not exist models mkdir models
call :download Qwen3-4B-Q4_K_M.gguf https://huggingface.co/ggml-org/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf || exit /b 1
call :download Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf https://huggingface.co/lmstudio-community/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf || exit /b 1
call :download mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf https://huggingface.co/lmstudio-community/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/mmproj-model-f16.gguf || exit /b 1
call :download gesture_recognizer.task https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task || exit /b 1
exit /b 0
:download
if exist "models\%~1" exit /b 0
curl.exe -fL -C - --retry 2 -o "models\%~1.part" "%~2" || exit /b 1
move /y "models\%~1.part" "models\%~1" >nul || exit /b 1
exit /b 0
