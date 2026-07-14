@echo off
setlocal
cd /d "%~dp0.."
python scripts\export_site.py
exit /b %ERRORLEVEL%
