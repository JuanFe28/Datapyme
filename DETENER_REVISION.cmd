@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\review_access.py stop
pause
