@echo off
rem Cria o ambiente Python (.venv) na raiz do projeto e instala as dependencias.
cd /d "%~dp0.."
if not exist "requirements.txt" (
  echo Arquivo requirements.txt ausente. Baixe a pasta completa do projeto.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m venv .venv
if errorlevel 1 goto fail_python
goto install
:use_python
python -m venv .venv
if errorlevel 1 goto fail_python
:install
if not exist ".venv\Scripts\python.exe" (
  goto fail_python
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo A instalacao falhou. Confira o erro acima e sua conexao.
  pause
  exit /b 1
)
echo Instalacao concluida. Abra scripts\iniciar_windows.bat.
pause
exit /b 0
:fail_python
echo Instale o Python 3.10 ou superior e tente novamente.
pause
exit /b 1
