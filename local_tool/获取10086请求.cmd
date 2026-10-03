@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0python\python.exe" -B -X utf8 run_capture.py
echo.
echo 结果会至少停留 10 秒，之后按任意键关闭窗口。
timeout /t 10 /nobreak >nul
pause
