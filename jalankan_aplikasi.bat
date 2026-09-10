@echo off
title Aplikasi Uji Gempa Miniatur Gedung
echo Membuka Aplikasi Desktop Uji Gempa...
python gui_app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Terjadi kendala saat membuka aplikasi.
    echo Memeriksa dependensi...
    pip install -r requirements.txt
    python gui_app.py
)
pause
