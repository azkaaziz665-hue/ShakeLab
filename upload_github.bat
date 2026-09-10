@echo off
title Upload ShakeLab ke GitHub
echo ============================================================
echo   UPLOAD SHAKELAB KE GITHUB
echo ============================================================
echo.
echo Pastikan Anda sudah:
echo   1. Membuat akun GitHub di https://github.com
echo   2. Membuat repository baru bernama "ShakeLab" (Public)
echo   3. Menginstal Git: https://git-scm.com/download/win
echo.
set /p GITHUB_USER=Masukkan username GitHub Anda: azkaaziz665-hue

echo.

REM Cek apakah Git terinstall
where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git tidak terinstall.
    echo Download dari: https://git-scm.com/download/win
    pause
    exit /b 1
)

REM Pastikan .gitignore ada
if not exist .gitignore (
    echo File .gitignore tidak ditemukan, membuat .gitignore bawaan...
    (
        echo __pycache__/
        echo *.pyc
        echo *.pyo
        echo *.pyd
        echo build/
        echo dist/
        echo *.spec
        echo result/
        echo *.csv
        echo *.xlsx
        echo grafik_*.png
        echo tabel_*.txt
        echo data_*.csv
        echo data_*.xlsx
        echo kualitas_*.json
        echo *.pfx
        echo *.p12
        echo ShakeLab_CodeSign.*
        echo *.log
        echo *.tmp
    ) > .gitignore
)

REM Inisialisasi dan hubungkan Git
if not exist .git (
    echo Menginisialisasi Git repository...
    git init
    git branch -M main
    git remote add origin https://github.com/%GITHUB_USER%/ShakeLab.git
    echo Menghubungkan ke repository GitHub yang sudah ada...
    git fetch origin main >nul 2>&1
    git reset origin/main >nul 2>&1
) else (
    git remote remove origin >nul 2>&1
    git remote add origin https://github.com/%GITHUB_USER%/ShakeLab.git
    git branch -M main
)

REM Input pesan commit
set "COMMIT_MSG="
set /p COMMIT_MSG=Masukkan pesan commit (kosongkan untuk default): 
if "%COMMIT_MSG%"=="" (
    set "COMMIT_MSG=Update ShakeLab: deteksi kamera otomatis dan pembaruan modul"
)

REM Tambahkan seluruh file proyek (mengikuti aturan .gitignore)
echo Menambahkan file proyek...
git add .
git commit -m "%COMMIT_MSG%"

REM Push ke GitHub
echo Mengunggah perubahan ke GitHub...
git push -u origin main

echo.
echo BERHASIL! Kode sudah diupload ke:
echo https://github.com/%GITHUB_USER%/ShakeLab
echo.
pause
