@echo off
title Asistente Inteligente de Outlook - Servidor Local
echo ============================================================
echo   Iniciando Asistente Inteligente de Correo Outlook
echo   Ejecucion 100%% Local - Puerto 8050
echo ============================================================
echo.
echo Iniciando servidor Python local y abriendo interfaz...

start /b python server.py
timeout /t 2 /nobreak >nul

start http://localhost:8050

echo.
echo [OK] Servidor corriendo. Puedes minimizar esta ventana.
echo Para detener el servidor, cierra esta ventana.
pause
