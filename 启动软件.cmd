@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\cao\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if not exist "%PYTHON_EXE%" (
  set "PYTHON_EXE=C:\Users\cao\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)
if not exist "%PYTHON_EXE%" (
  echo 未找到本机 Python 运行环境，请改用 EXE 或重新安装依赖。
  pause
  exit /b 1
)
"%PYTHON_EXE%" -m simultaneous_interpreter.desktop_launcher
endlocal
