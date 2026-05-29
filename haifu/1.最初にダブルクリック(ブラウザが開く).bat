@echo off
chcp 65001 > nul

:: Chromeのパスを探す
SET CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
IF EXIST "%CHROME_PATH%" GOTO FOUND

SET CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
IF EXIST "%CHROME_PATH%" GOTO FOUND

FOR /F "tokens=2*" %%A IN ('REG QUERY "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') DO SET CHROME_PATH=%%B
IF EXIST "%CHROME_PATH%" GOTO FOUND

FOR /F "tokens=2*" %%A IN ('REG QUERY "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') DO SET CHROME_PATH=%%B
IF EXIST "%CHROME_PATH%" GOTO FOUND

echo Chromeが見つかりません。Chromeをインストールしてください。
pause
exit /b 1

:FOUND
pushd "%~dp0"
setlocal EnableDelayedExpansion

REM Load URLs from urls.txt (token kept out of git).
set URLFILE=urls.txt
if not exist "%URLFILE%" (
    if exist "urls.example.txt" (
        copy "urls.example.txt" "%URLFILE%" >nul
        echo urls.txt was not found, so a template was created.
        echo Please open it and fill in the real SUUMO token, then run this again.
        notepad "%URLFILE%"
        endlocal & popd & pause & exit /b 0
    )
    echo ERROR: urls.txt and template are both missing.
    endlocal & popd & pause & exit /b 1
)

set URLS=
for /f "usebackq tokens=* delims=" %%U in ("%URLFILE%") do (
    set "line=%%U"
    if not "!line!"=="" if not "!line:~0,1!"=="#" set URLS=!URLS! "%%U"
)

echo Chrome起動中...（デバッグポート: 9222）
SET PROFILE_DIR=%LOCALAPPDATA%\syayuu_nyuuryoku_chrome
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%PROFILE_DIR%" !URLS!
endlocal & popd
