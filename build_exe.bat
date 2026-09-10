@echo off
title Membangun File EXE - ShakeLab
echo ========================================================
echo   MEMBUAT FILE STANDALONE EXE (PyInstaller) - ShakeLab
echo ========================================================
echo.

echo 1. Memeriksa pustaka PyInstaller...
python -m pip install pyinstaller PyQt6 pyqtgraph openpyxl matplotlib opencv-contrib-python

echo.
echo 2. Memulai proses build dengan PyInstaller...
echo Mohon tunggu beberapa saat...
echo.

python -m PyInstaller --noconfirm --onedir --windowed ^
    --name "ShakeLab" ^
    --icon "logo.ico" ^
    --add-data "logo.png;." ^
    --add-data "logo.ico;." ^
    --add-data "arrow_up.png;." ^
    --add-data "arrow_down.png;." ^
    --collect-all pyqtgraph ^
    --collect-all cv2 ^
    gui_app.py

echo.
echo ========================================================
if exist "dist\ShakeLab\ShakeLab.exe" (
    echo   BERHASIL! File EXE telah dibuat di folder:
    echo   dist\ShakeLab\ShakeLab.exe
) else (
    echo   Terjadi kendala saat build. Silakan periksa pesan di atas.
)
echo ========================================================
echo.
pause
