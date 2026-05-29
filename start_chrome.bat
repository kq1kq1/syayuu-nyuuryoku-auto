@echo off

REM Try standard Chrome paths
SET CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
IF EXIST "%CHROME_PATH%" GOTO FOUND

SET CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
IF EXIST "%CHROME_PATH%" GOTO FOUND

REM Search registry for Chrome path
FOR /F "tokens=2*" %%A IN ('REG QUERY "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') DO SET CHROME_PATH=%%B
IF EXIST "%CHROME_PATH%" GOTO FOUND

FOR /F "tokens=2*" %%A IN ('REG QUERY "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') DO SET CHROME_PATH=%%B
IF EXIST "%CHROME_PATH%" GOTO FOUND

echo Chrome not found.
echo Please check your Chrome installation path.
pause
exit /b 1

:FOUND
pushd "%~dp0"
setlocal EnableDelayedExpansion

REM Load URLs from config\urls.txt (token kept out of git).
set URLFILE=config\urls.txt
if not exist "%URLFILE%" (
    if exist "config\urls.example.txt" (
        copy "config\urls.example.txt" "%URLFILE%" >nul
        echo config\urls.txt was not found, so a template was created.
        echo Please open it and fill in the real SUUMO token, then run this again.
        notepad "%URLFILE%"
        endlocal & popd & pause & exit /b 0
    )
    echo ERROR: config\urls.txt and template are both missing.
    endlocal & popd & pause & exit /b 1
)

REM Build URL argument list (skip blank lines and # comments).
set URLS=
for /f "usebackq tokens=* delims=" %%U in ("%URLFILE%") do (
    set "line=%%U"
    if not "!line!"=="" if not "!line:~0,1!"=="#" set URLS=!URLS! "%%U"
)

echo Chrome found: %CHROME_PATH%
echo Starting Chrome with debug port 9222...
SET PROFILE_DIR=%LOCALAPPDATA%\syayuu_nyuuryoku_chrome
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%PROFILE_DIR%" !URLS!
echo Done.
endlocal & popd
