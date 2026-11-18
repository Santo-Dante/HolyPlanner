@echo off
rem Servidor para navegador e celular na rede local (codigo-fonte).
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Execute scripts\instalar_windows.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py --web --lan
pause
