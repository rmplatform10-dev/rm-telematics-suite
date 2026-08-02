@echo off
REM Portable deploy/launch helper for RM Telematics Suite
setlocal
set ROOT_DIR=%~dp0nREM Run cleanup first
call "%ROOT_DIR%cleanup.bat"nREM Start gateway (if present) - best-effort: look for gateway_listener.pynif exist "%ROOT_DIR%gateway\gateway_listener.py" (
    start "Gateway" cmd /c "py -3 "%ROOT_DIR%gateway\gateway_listener.py" || python "%ROOT_DIR%gateway\gateway_listener.py""
)
nREM Start Dashboard using Start_Dashboard.bat
call "%ROOT_DIR%Start_Dashboard.bat"
endlocal
