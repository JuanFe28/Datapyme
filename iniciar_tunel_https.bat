@echo off
chcp 65001 > nul
title Tunel HTTPS Movil - Datapyme Empresarial
echo =========================================================================
echo       DATAPYME EMPRESARIAL - TUNEL PUBLICO SEGURO HTTPS
echo =========================================================================
echo  Conectando puerto local 8000 a la red global Cloudflare...
echo  Copia la URL https://*.trycloudflare.com que aparezca abajo en tu celular.
echo =========================================================================
echo.
"%~dp0\.local\tools\cloudflared.exe" tunnel --url http://127.0.0.1:8000 --http-host-header 127.0.0.1 --protocol http2 --no-autoupdate
pause
