@echo off
REM Script de un click para regenerar el HTML y publicarlo en GitHub Pages.
REM Antes de correr esto, EDITAR data.json con las designaciones del nuevo mes.

cd /d "%~dp0"

echo.
echo ===============================================
echo  Designaciones Multimedia SPLN - Publicador
echo ===============================================
echo.

echo [1/4] Generando index.html desde data.json...
python generate.py
if errorlevel 1 (
    echo ERROR: fallo el generador. Revisa data.json.
    pause
    exit /b 1
)

echo.
echo [2/4] Estado del repo:
git status -s

echo.
set /p commit_msg="Mensaje del commit (ej: Junio 2026): "
if "%commit_msg%"=="" (
    echo ERROR: necesitas un mensaje de commit.
    pause
    exit /b 1
)

echo.
echo [3/4] Commiteando cambios...
git add data.json index.html
git commit -m "%commit_msg%"

echo.
echo [4/4] Subiendo a GitHub...
git push

echo.
echo ===============================================
echo  Listo! En 1-2 min se actualiza el sitio:
echo  https://axelitoteca.github.io/spln-multimedia/
echo ===============================================
echo.
pause
