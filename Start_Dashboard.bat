@echo off
REM Start from the script directory so relative paths work
pushd "%~dp0"
echo Starting RM Telematics Dashboard...
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  start "Dashboard Server" py -3 dashboard\server.py
) else (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    start "Dashboard Server" python dashboard\server.py
  ) else (
    echo ERROR: No Python runtime found (py or python not in PATH)
  )
)

timeout /t 2 >nul
start "" http://localhost:8080
echo Dashboard is live at http://localhost:8080
echo Gateway is running in the background.
popd
pause
