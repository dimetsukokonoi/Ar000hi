@echo off
REM Arooohi - one-command launcher for Windows.
REM Wraps the cross-platform launcher (launch.py) and forwards all arguments.

setlocal
set ROOT=%~dp0

REM Locate a Python 3 interpreter.
set PY=py
py -3 --version >nul 2>&1 && set PY=py -3
if errorlevel 1 (
  python --version >nul 2>&1 && set PY=python
)
if errorlevel 1 (
  echo [Arooohi error] Python 3 was not found. Install it from https://python.org and re-run.
  exit /b 1
)

%PY% "%ROOT%launch.py" %*
endlocal