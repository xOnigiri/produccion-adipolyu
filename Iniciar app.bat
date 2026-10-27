@echo off
rem Arranca la app de produccion Adipolyu y abre el navegador en el formulario.
title Produccion Adipolyu - no cierres esta ventana mientras uses la app
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv en esta carpeta.
    echo Sin el no se puede abrir la app.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" app.py --abrir-navegador

echo.
echo La app se cerro.
pause
