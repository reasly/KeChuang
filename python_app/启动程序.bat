@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=%~dp0runtime\python.exe"

if not exist "%PY%" (
  echo 未找到本地 Python：
  echo   %PY%
  echo.
  echo 请先双击运行“安装依赖.bat”。它会把便携 Python 装到本目录 runtime\，
  echo 不依赖系统里是否安装过 Python。
  pause
  exit /b 1
)

echo 使用本地 Python：%PY%
"%PY%" "%~dp0app.py"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo 程序退出码 %EXIT_CODE%。
  pause
)
exit /b %EXIT_CODE%
