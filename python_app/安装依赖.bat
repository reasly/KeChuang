@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "RUNTIME=%~dp0runtime"
set "PY=%RUNTIME%\python.exe"
set "INSTALLER=%TEMP%\kechuang-python-setup.exe"
set "PY_VERSION=3.12.10"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe"

echo [1/2] 检查本地 Python ...
if exist "%PY%" goto :install_deps

echo 未找到 runtime\python.exe，正在安装便携 Python 到本目录（不改系统 PATH）...
echo 下载：%PY_URL%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%INSTALLER%' -UseBasicParsing } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
  echo 下载 Python 失败，请检查网络后重试。
  pause
  exit /b 1
)

echo 正在解压安装到：
echo   %RUNTIME%
"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_pip=1 SimpleInstall=1 TargetDir="%RUNTIME%"
set "INSTALL_EXIT=%ERRORLEVEL%"
del /q "%INSTALLER%" >nul 2>&1

if not exist "%PY%" (
  echo 本地 Python 安装失败，退出码 %INSTALL_EXIT%。
  pause
  exit /b 1
)

echo 本地 Python 已就绪：%PY%

:install_deps
echo [2/2] 安装项目依赖 ...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 (
  echo pip 升级失败。
  pause
  exit /b 1
)
"%PY%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo 依赖安装失败。
  pause
  exit /b 1
)

echo.
echo 完成。以后请双击“启动程序.bat”，将使用本地 runtime\python.exe。
pause
exit /b 0
