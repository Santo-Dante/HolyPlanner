@echo off
rem Gera o executavel em dist\v5.0\Holy Planner com PyInstaller.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" call scripts\instalar_windows.bat
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.16,<7"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath dist\v5.0 "Holy Planner.spec"
if errorlevel 1 exit /b 1
for %%f in (APP.md TREINOS.md PLANEJAMENTO.md ROTINA.md ACESSO_REMOTO.md GOOGLE_AGENDA.md INVESTIDOR10.md) do copy /y "docs\%%f" "dist\v5.0\Holy Planner\%%f"
copy /y scripts\iniciar_celular.bat "dist\v5.0\Holy Planner\iniciar_celular.bat"
echo Pronto: dist\v5.0\Holy Planner\Holy Planner.exe
pause
