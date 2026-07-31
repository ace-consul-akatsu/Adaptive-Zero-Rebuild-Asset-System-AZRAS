@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "LOG=%ROOT%\AZRAS_Platform_Core_v3_3_0_build_log.txt"
set "DIST=%ROOT%\dist_AZRAS_Platform_Core_v3_3_0"
set "BUILD=%ROOT%\build_AZRAS_Platform_Core_v3_3_0"
set "EXE=%DIST%\AZRAS_Platform_Core_v3_3_0\AZRAS_Platform_Core_v3_3_0.exe"

> "%LOG%" echo AZRAS Platform Core v3.3.0 Build Log
taskkill /F /IM AZRAS_Platform_Core_v3_2_2.exe >>"%LOG%" 2>&1
taskkill /F /IM AZRAS_Platform_Core_v3_3_0.exe >>"%LOG%" 2>&1

if exist "%BUILD%" rmdir /S /Q "%BUILD%"
if exist "%DIST%" rmdir /S /Q "%DIST%"

python -m pip install --upgrade pyinstaller reportlab pypdf numpy pandas pymupdf opencv-python pillow >>"%LOG%" 2>&1
if errorlevel 1 goto FAILED

python -m PyInstaller --noconfirm --clean --windowed ^
 --name AZRAS_Platform_Core_v3_3_0 ^
 --distpath "%DIST%" ^
 --workpath "%BUILD%" ^
 --add-data "%ROOT%\lang;lang" ^
 --add-data "%ROOT%\data;data" ^
 --hidden-import cv2 ^
 --hidden-import fitz ^
 --hidden-import PIL ^
 "%ROOT%\main.py" >>"%LOG%" 2>&1

if errorlevel 1 goto FAILED
if not exist "%EXE%" goto FAILED

echo Build completed successfully.
explorer /select,"%EXE%"
pause
exit /b 0

:FAILED
echo Build failed. Check:
echo %LOG%
pause
exit /b 1
