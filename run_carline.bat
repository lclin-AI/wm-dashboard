@echo off
REM 一日一次：車線 + 地址冇車線（~90 + ~280 個 request，約 6 分鐘），然後 push。
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY="C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.13_3.13.3824.0_x64__qbz5n2kfra8p0\python3.13.exe"
if not exist %PY% set PY=python
%PY% collect.py --carline --zonegap >> "%~dp0collect.log" 2>&1
%PY% publish.py >> "%~dp0collect.log" 2>&1
