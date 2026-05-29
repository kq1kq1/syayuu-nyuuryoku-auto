@echo off
chcp 932 > nul
pushd "%~dp0"

set LOGFILE=setup.log
echo Setup started: %date% %time% > "%LOGFILE%"

echo.
echo =============================================
echo  Shayuu Nyuuryoku Bot - Setup (first run only)
echo =============================================
echo.
echo This window will NOT close automatically.
echo.

:: Warn if running inside Dropbox/OneDrive (causes file lock errors)
echo %CD% | findstr /I "Dropbox OneDrive" >nul
if not errorlevel 1 (
    echo ===============================================================
    echo  WARNING: Running inside Dropbox/OneDrive folder!
    echo  Sync may LOCK files and break setup.
    echo  RECOMMENDED: Move this folder to C:\Users\YourName\Desktop\
    echo  before continuing.
    echo  Current path: %CD%
    echo ===============================================================
    echo.
)

echo Press any key to start setup...
pause > nul
echo.

set ERRMSG=

call :main
goto :end


:main

:: ---- [1/3] Python embeddable ----
if exist "python\python.exe" (
    echo [1/3] Python already exists. Skipping download.
    echo [1/3] Python already exists. Skipping download. >> "%LOGFILE%"
    goto :install_pip
)

echo [1/3] Downloading Python (30s-2min)...
echo [1/3] Downloading Python... >> "%LOGFILE%"
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python_embed.zip' -UseBasicParsing } catch { Write-Host ('Download error: ' + $_.Exception.Message); exit 1 }" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    set ERRMSG=Python download failed. Check internet / proxy / antivirus.
    goto :eof
)
if not exist "python_embed.zip" (
    set ERRMSG=python_embed.zip was not created.
    goto :eof
)

echo Extracting Python...
echo Extracting Python... >> "%LOGFILE%"
powershell -NoProfile -Command "try { Expand-Archive -Path 'python_embed.zip' -DestinationPath 'python' -Force } catch { Write-Host ('Extract error: ' + $_.Exception.Message); exit 1 }" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    set ERRMSG=Extraction failed. Windows Defender may have quarantined python.exe.
    goto :eof
)
del python_embed.zip 2>nul

if not exist "python\python.exe" (
    set ERRMSG=python.exe missing. Check Defender protection history.
    goto :eof
)

:: Enable import site in ._pth (with retry for Dropbox/OneDrive lock)
echo Patching python._pth (enabling import site)...
echo Patching python._pth... >> "%LOGFILE%"
powershell -NoProfile -Command "$ok=$false; for($i=1;$i -le 10;$i++){ try { Get-ChildItem 'python\*._pth' | ForEach-Object { $c=(Get-Content $_.FullName) -replace '#import site','import site'; Set-Content -Path $_.FullName -Value $c -Force -ErrorAction Stop }; $ok=$true; break } catch { Write-Host ('Retry ' + $i + ': ' + $_.Exception.Message); Start-Sleep -Seconds 2 } }; if(-not $ok){ exit 1 }" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    set ERRMSG=Could not patch python._pth. File locked by Dropbox/OneDrive. Move folder out of Dropbox and retry.
    goto :eof
)

:: Verify import site is enabled
findstr /C:"import site" python\*._pth >nul 2>&1
if errorlevel 1 (
    set ERRMSG=python._pth patch verification failed. Move folder out of Dropbox/OneDrive and retry.
    goto :eof
)
echo Python extraction OK.
echo Python extraction OK. >> "%LOGFILE%"


:install_pip
:: ---- [2/3] pip ----
echo.
echo [2/3] Installing pip...
echo [2/3] Installing pip... >> "%LOGFILE%"
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py' -UseBasicParsing } catch { Write-Host ('get-pip download error: ' + $_.Exception.Message); exit 1 }" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    set ERRMSG=get-pip.py download failed.
    goto :eof
)
python\python.exe get-pip.py >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    set ERRMSG=pip install failed. See end of setup.log.
    goto :eof
)
del get-pip.py 2>nul


:: ---- [3/3] libraries ----
echo.
echo [3/3] Installing playwright and openpyxl...
echo [3/3] Installing playwright and openpyxl... >> "%LOGFILE%"
python\python.exe -m pip install playwright openpyxl >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    set ERRMSG=playwright / openpyxl install failed. See setup.log.
    goto :eof
)

echo.
echo =============================================
echo  Setup complete!
echo  Next: double-click "2.tsugini..." to launch
echo =============================================
echo Setup complete. >> "%LOGFILE%"
goto :eof


:end
echo.
echo =============================================
if defined ERRMSG (
    echo  *** ERROR: setup stopped
    echo  *** Reason: %ERRMSG%
    echo.
    echo  Open setup.log for details:
    echo  %CD%\setup.log
) else (
    echo  Finished successfully.
)
echo =============================================
echo.
echo (This window stays open until you press a key)
pause
popd
