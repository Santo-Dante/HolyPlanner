@echo off
rem Abre a janela desktop do Holy Planner.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Execute scripts\instalar_windows.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
