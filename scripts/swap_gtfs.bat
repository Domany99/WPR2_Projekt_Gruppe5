@echo off
REM Skript zum Austauschen der GTFS-Datei für OTP

echo ============================================================
echo GTFS-Datei Austausch fuer OTP
echo ============================================================
echo.

cd /d "%~dp0.."

REM 1. Original sichern (falls noch nicht geschehen)
if exist "otp\graphs\bern\gtfs_full_backup.zip" (
    echo [INFO] Backup existiert bereits: gtfs_full_backup.zip
) else (
    echo [1/3] Sichere Original-GTFS...
    move "otp\graphs\bern\gtfs_fp2025_20251101.zip" "otp\graphs\bern\gtfs_full_backup.zip"
    if errorlevel 1 (
        echo [FEHLER] Konnte Original nicht sichern!
        pause
        exit /b 1
    )
    echo       -> Gesichert als gtfs_full_backup.zip
)

REM 2. Gefilterte Datei umbenennen
echo.
echo [2/3] Verwende gefilterte GTFS-Datei...
copy "otp\graphs\bern\gtfs_bern_filtered.zip" "otp\graphs\bern\gtfs_fp2025_20251101.zip"
if errorlevel 1 (
    echo [FEHLER] Konnte gefilterte Datei nicht kopieren!
    pause
    exit /b 1
)
echo       -> gtfs_fp2025_20251101.zip (gefiltert)

REM 3. Fertig
echo.
echo [3/3] Fertig!
echo.
echo ============================================================
echo NAECHSTE SCHRITTE:
echo ============================================================
echo.
echo Starte OTP neu mit:
echo   docker-compose down
echo   docker-compose up --build
echo.
echo Oder falls OTP nicht läuft:
echo   docker-compose up
echo.
echo ============================================================
pause

