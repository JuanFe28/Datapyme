@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno Python de esta instalacion. Consulta README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\review_access.py start
if errorlevel 1 (
  echo No se confirmo el acceso de revision. Revisa el mensaje anterior.
) else (
  echo Comparte solo con tu companero el enlace y acceso del TXT privado.
  if exist "USO_PRIVADO_EQUIPO.txt" (
    start "" notepad.exe "USO_PRIVADO_EQUIPO.txt"
  ) else (
    start "" notepad.exe ".local\review\ACCESO_REVISION.txt"
  )
)
pause
