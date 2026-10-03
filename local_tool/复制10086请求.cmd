@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0python\python.exe" -B -X utf8 export_capture.py
echo.
pause
