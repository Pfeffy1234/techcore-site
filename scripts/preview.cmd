@echo off
setlocal
cd /d "%~dp0.."
if not exist "dist\index.html" (
  echo dist\ fehlt — zuerst exportieren: python scripts\export_site.py
  exit /b 1
)
echo Lokale Vorschau: http://localhost:8080
echo Beenden mit Strg+C
py -m http.server 8080 --directory dist
