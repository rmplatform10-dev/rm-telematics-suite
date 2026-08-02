@echo off
echo Starting RM Telematics Dashboard...
<<<<<<< HEAD
start "Dashboard Server" py -3.12 "%~dp0dashboard\server.py"
=======
start "Dashboard Server" cmd /c "py -3 "%~dp0dashboard\server.py" || python "%~dp0dashboard\server.py""
>>>>>>> c0fe9f2 (chore: deep upgrade — portable dashboard, cleanup/deploy helpers, .gitignore and small runtime config\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>)
timeout /t 2 >nul
start "" http://localhost:8080
echo Dashboard is live at http://localhost:8080
echo Gateway is running in the background.
pause
