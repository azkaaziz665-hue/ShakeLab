@echo off
title Code Signing - ShakeLab
echo ============================================================
echo   PENANDATANGANAN DIGITAL (CODE SIGNING) - ShakeLab
echo ============================================================
echo.
echo Pilih metode:
echo   [1] Self-Signed (GRATIS) - untuk distribusi internal/testing
echo   [2] Petunjuk membeli sertifikat resmi (OV/EV)
echo   [3] Tanda tangani EXE yang ada (jika sudah punya sertifikat .pfx)
echo.
set /p CHOICE=Pilihan Anda (1/2/3): 

if "%CHOICE%"=="1" goto SELF_SIGNED
if "%CHOICE%"=="2" goto BUY_CERT
if "%CHOICE%"=="3" goto SIGN_WITH_PFX
goto END

:SELF_SIGNED
echo.
echo ============================================================
echo   MEMBUAT SERTIFIKAT SELF-SIGNED
echo ============================================================
echo.

REM Cari PowerShell
where powershell >nul 2>&1
if errorlevel 1 (
    echo ERROR: PowerShell tidak ditemukan.
    goto END
)

echo Membuat sertifikat self-signed via PowerShell...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  " = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=ShakeLab Developer' -KeyUsage DigitalSignature -FriendlyName 'ShakeLab Code Signing' -CertStoreLocation 'Cert:\CurrentUser\My' -NotAfter (Get-Date).AddYears(5); Write-Host ('Sertifikat dibuat: ' + .Thumbprint); C:\Users\LoQ\Documents\uji bangunan = ConvertTo-SecureString -String 'ShakeLab123!' -Force -AsPlainText; Export-PfxCertificate -Cert  -FilePath 'ShakeLab_CodeSign.pfx' -Password C:\Users\LoQ\Documents\uji bangunan; Write-Host 'File ShakeLab_CodeSign.pfx berhasil dibuat dengan password: ShakeLab123!'"

echo.
echo Menandatangani ShakeLab.exe...
set SIGNTOOL=
for /f "delims=" %%i in ('where signtool 2^>nul') do set SIGNTOOL=%%i

if "%SIGNTOOL%"=="" (
    REM Cari di lokasi umum Windows SDK
    for %%d in (
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe"
        "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
    ) do (
        if exist %%d set SIGNTOOL=%%d
    )
)

if "%SIGNTOOL%"=="" (
    echo.
    echo PERINGATAN: signtool.exe tidak ditemukan.
    echo Install Windows SDK dari:
    echo https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
    goto END
)

echo Menggunakan: %SIGNTOOL%
echo.
"%SIGNTOOL%" sign /f "ShakeLab_CodeSign.pfx" /p "ShakeLab123!" /fd SHA256 /t "http://timestamp.digicert.com" "dist\ShakeLab\ShakeLab.exe"

if errorlevel 1 (
    echo GAGAL: Proses tanda tangan gagal. Pastikan ShakeLab.exe ada di dist\ShakeLab\
) else (
    echo.
    echo BERHASIL! ShakeLab.exe sudah ditandatangani.
    echo.
    echo LANGKAH SELANJUTNYA untuk distribusi internal:
    echo   1. Kirimkan file 'ShakeLab_CodeSign.pfx' ke pengguna
    echo   2. Pengguna install sertifikat: klik 2x .pfx ^> Install ^> Trusted Root CA
    echo   3. Setelah itu SmartScreen tidak akan muncul lagi di PC tersebut
)
goto END

:BUY_CERT
echo.
echo ============================================================
echo   PANDUAN MEMBELI SERTIFIKAT RESMI
echo ============================================================
echo.
echo REKOMENDASI PENYEDIA (dari termurah):
echo.
echo   1. SignMyCode.com   - mulai /tahun (OV)
echo      https://signmycode.com/
echo.
echo   2. SSL.com          - mulai /tahun (OV) / /tahun (EV)
echo      https://www.ssl.com/certificates/ev-code-signing/
echo.
echo   3. Sectigo/Comodo   - mulai /tahun (OV)
echo      https://sectigo.com/
echo.
echo SETELAH MEMBELI:
echo   - Anda akan mendapat file .pfx atau USB Hardware Token (EV)
echo   - Jalankan script ini lagi pilih opsi [3]
echo.
goto END

:SIGN_WITH_PFX
echo.
echo ============================================================
echo   TANDA TANGANI DENGAN SERTIFIKAT .PFX YANG ADA
echo ============================================================
echo.
set /p PFX_PATH=Masukkan path file .pfx Anda: 
set /p PFX_PASS=Masukkan password .pfx: 
echo.

set SIGNTOOL=
for /f "delims=" %%i in ('where signtool 2^>nul') do set SIGNTOOL=%%i

if "%SIGNTOOL%"=="" (
    for %%d in (
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe"
        "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
    ) do (
        if exist %%d set SIGNTOOL=%%d
    )
)

if "%SIGNTOOL%"=="" (
    echo ERROR: signtool.exe tidak ditemukan.
    echo Install Windows SDK dari: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
    goto END
)

echo Menandatangani ShakeLab.exe...
"%SIGNTOOL%" sign /f "%PFX_PATH%" /p "%PFX_PASS%" /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 "dist\ShakeLab\ShakeLab.exe"

if errorlevel 1 (
    echo GAGAL: Periksa path .pfx dan password Anda.
) else (
    echo.
    echo BERHASIL! ShakeLab.exe sudah ditandatangani secara resmi.
    echo Distribusikan file di dist\ShakeLab\ kepada pengguna.
    echo SmartScreen TIDAK akan muncul (EV cert) atau akan hilang setelah
    echo beberapa pengguna menjalankan aplikasi (OV cert).
)
goto END

:END
echo.
pause
