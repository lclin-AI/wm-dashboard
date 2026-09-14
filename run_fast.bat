@echo off
REM 每 5 分鐘：時段（讀 monitor snapshot）+ District Quota，然後 push。
REM ⚠ 一定要用真實 exe 路徑，唔可以用 `python` —— 佢係 WindowsApps 嘅
REM App Execution Alias，Session 0 解析唔到（wm-quota-monitor 2026-09-14 中過）。
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY="C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.13_3.13.3824.0_x64__qbz5n2kfra8p0\python3.13.exe"
if not exist %PY% set PY=python
%PY% collect.py --timeslots --district >> "%~dp0collect.log" 2>&1
%PY% publish.py >> "%~dp0collect.log" 2>&1
