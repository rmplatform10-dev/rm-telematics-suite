@echo off
echo Starting RM Telematics Dashboard...
start "Dashboard Server" cmd /c "py -3 "%~dp0dashboard\server.py" || python "%~dp0dashboard\server.py""
timeout /t 2 >nul
start "" http://localhost:8080
echo Dashboard is live at http://localhost:8080
echo Gateway is running in the background.
pause
