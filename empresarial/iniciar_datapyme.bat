@echo off
chcp 65001 > nul
title Datapyme Empresarial SaaS (F-DC-124)

:: Localizar la carpeta empresarial
if exist "%~dp0\empresarial\app\main.py" (
    cd /d "%~dp0\empresarial"
) else if exist "%~dp0\app\main.py" (
    cd /d "%~dp0"
)

echo =========================================================================
echo       DATAPYME EMPRESARIAL - PLATAFORMA ANALITICA COMERCIAL PYME
echo =========================================================================
echo  Iniciando servidor local en http://127.0.0.1:8000 ...
echo  Abriendo navegador predeterminado...
echo  Para detener el servidor, cierre esta ventana o presione Ctrl + C.
echo =========================================================================
echo.

:: Abrir navegador en 2 segundos en segundo plano
start /b "" powershell -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000/login'"

:: Ejecutar servidor uvicorn con el entorno virtual
if exist ".\.venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) else (
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
)

pause
