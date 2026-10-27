@echo off
rem Abre la app en MODO PRUEBA: usa produccion_prueba.db con datos de ejemplo.
rem Nunca toca produccion.db. Sirve para practicar y para mostrar la app.
rem Para volver a los datos de ejemplo iniciales, borra produccion_prueba.db.
title MODO PRUEBA - Produccion Adipolyu (datos de ejemplo)
color 6F
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv en esta carpeta.
    echo Sin el no se puede abrir la app.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" app.py --modo-prueba --abrir-navegador

echo.
echo La app de prueba se cerro.
pause
