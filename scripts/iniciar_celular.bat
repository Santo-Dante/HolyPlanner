@echo off
rem Copiado ao lado do executavel pelo gerar_app_windows.bat; no codigo-fonte usa iniciar_web.bat.
cd /d "%~dp0"
if exist "Holy Planner.exe" (
  start "" "Holy Planner.exe" --web --lan
) else (
  call "%~dp0iniciar_web.bat"
)
