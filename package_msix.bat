@echo off
title Packaging ShakeLab sebagai MSIX untuk Microsoft Store
echo ============================================================
echo   PACKAGING SHAKELAB - MSIX untuk Microsoft Store
echo ============================================================
echo.

REM ---- Konfigurasi ----
set APP_NAME=ShakeLab
set APP_VERSION=2.4.0.0
set DIST_DIR=dist\ShakeLab
set OUTPUT_DIR=dist\MSIX_Output

echo [1/5] Memeriksa apakah build EXE sudah ada...
if not exist "%DIST_DIR%\ShakeLab.exe" (
    echo   ERROR: ShakeLab.exe tidak ditemukan di %DIST_DIR%
    echo   Jalankan dulu: build_exe.bat
    pause
    exit /b 1
)
echo   OK - ShakeLab.exe ditemukan.
echo.

echo [2/5] Menyiapkan folder output MSIX...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%DIST_DIR%\Assets" mkdir "%DIST_DIR%\Assets"
echo   OK - Folder Assets dibuat.
echo.

echo [3/5] Menyalin AppxManifest.xml ke folder build...
copy /Y "AppxManifest.xml" "%DIST_DIR%\AppxManifest.xml"
echo   OK - Manifest disalin.
echo.

echo [4/5] Membuat gambar aset placeholder (Assets)...
echo   CATATAN: Ganti file-file di %DIST_DIR%\Assets\ dengan gambar resmi Anda!
echo   Format yang dibutuhkan:
echo     - StoreLogo.png         (50x50 px)
echo     - Square44x44Logo.png   (44x44 px)
echo     - Square150x150Logo.png (150x150 px)
echo     - Wide310x150Logo.png   (310x150 px)
echo     - Square310x310Logo.png (310x310 px)
echo     - SplashScreen.png      (620x300 px)
echo.

REM Copy logo.png sebagai placeholder sementara
for %%f in (StoreLogo Square44x44Logo Square150x150Logo Wide310x150Logo Square310x310Logo SplashScreen) do (
    copy /Y "logo.png" "%DIST_DIR%\Assets\%%f.png" >nul 2>&1
)
echo   OK - Aset placeholder disalin dari logo.png
echo.

echo [5/5] Petunjuk langkah selanjutnya:
echo ============================================================
echo   A. Install MSIX Packaging Tool dari Microsoft Store:
echo      https://www.microsoft.com/store/productId/9N5LW3JBCXKF
echo.
echo   B. Buka MSIX Packaging Tool ^> "Package Editor"
echo      Pilih folder: %DIST_DIR%
echo      Tool akan membaca AppxManifest.xml secara otomatis.
echo.
echo   C. Atau gunakan MakeAppx.exe (Windows SDK):
echo      MakeAppx.exe pack /d "%DIST_DIR%" /p "%OUTPUT_DIR%\ShakeLab.msix"
echo.
echo   D. Setelah .msix dibuat, tanda tangani dengan SignTool:
echo      SignTool.exe sign /fd SHA256 /a "%OUTPUT_DIR%\ShakeLab.msix"
echo.
echo   E. Upload ke Partner Center:
echo      https://partner.microsoft.com/dashboard
echo ============================================================
echo.
pause
