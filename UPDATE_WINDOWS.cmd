@echo off
setlocal
set "SRC=%~dp0kitchen_book"
set "DST=%USERPROFILE%\Downloads\Kitchen-RecipeBook-Pi\AI-Core-Project-master\kitchen_book"
if not "%~1"=="" set "DST=%~f1"
if not exist "%DST%\source\app.py" goto :missing
if not exist "%SRC%\raspberrypi\camera_server.py" goto :missing
if /i "%SRC%"=="%DST%" goto :upload
for %%F in ("%SRC%\source\*.py") do (
  copy /Y "%%~fF" "%DST%\source\" >nul || goto :failed
)
xcopy "%SRC%\source\static\*" "%DST%\source\static\" /E /I /Y /Q >nul || goto :failed
copy /Y "%SRC%\raspberrypi\camera_server.py" "%DST%\raspberrypi\" >nul || goto :failed
:upload
scp "%DST%\raspberrypi\camera_server.py" pi@70.12.226.174:~/kitchen_book/raspberrypi/ || goto :failed
scp "%DST%\source\device.py" pi@70.12.226.174:~/kitchen_book/source/ || goto :failed
echo UPDATE OK - restart the Pi server and Windows server.
pause
exit /b 0
:missing
echo Project not found. Extract the complete ZIP first. Pass the installed kitchen_book folder as argument if needed.
:failed
echo Update incomplete. See the error above.
pause
exit /b 1
