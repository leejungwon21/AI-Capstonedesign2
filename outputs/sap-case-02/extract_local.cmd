@echo off
setlocal
set "CAPSTONE_PYTHON=%~dp0..\..\work\slack-mcp-venv\Scripts\python.exe"
if not exist "%CAPSTONE_PYTHON%" (
  echo Python environment missing.
  pause
  exit /b 1
)
"%CAPSTONE_PYTHON%" "%~dp0extract_local.py"
pause
