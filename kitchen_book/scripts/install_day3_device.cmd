@echo off
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
 echo Usage: scripts\install_day3_device.cmd user@PI_IP
 exit /b 1
)
ssh "%~1" "mkdir -p ~/kitchen_book/raspberrypi ~/kitchen_book/source ~/kitchen_book/scripts ~/kitchen_book/models" || exit /b 1
scp raspberrypi\camera_server.py raspberrypi\voice_input.py raspberrypi\voice_llm.py "%~1:~/kitchen_book/raspberrypi/" || exit /b 1
scp source\device.py source\kitchen_commands.py source\day3.py "%~1:~/kitchen_book/source/" || exit /b 1
scp scripts\setup_day3_pi.sh "%~1:~/kitchen_book/scripts/" || exit /b 1
echo Files copied.
