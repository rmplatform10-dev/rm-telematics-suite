@echo off
REM Cleanup script - removes __pycache__ and .pyc files (dry-run when called with /n)
setlocal enabledelayedexpansionnset ROOT=%~dp0nif "%1"=="/n" (
  echo Dry-run: listing files that would be removed...
  for /f "delims=" %%F in ('dir /s /b "%ROOT%\__pycache__" 2^>nul') do echo %%F
  for /f "delims=" %%F in ('dir /s /b "%ROOT%\*.pyc" 2^>nul') do echo %%F
  goto :eof
)nfor /f "delims=" %%D in ('dir /s /b /ad "%ROOT%__pycache__" 2^>nul') do (
  echo Removing %%D
  rd /s /q "%%D"
)nfor /f "delims=" %%F in ('dir /s /b "%ROOT%*.pyc" 2^>nul') do (
  echo Deleting %%F
  del /f /q "%%F"
)necho Cleanup complete.
endlocal
