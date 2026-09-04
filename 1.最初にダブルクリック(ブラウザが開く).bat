@echo off
REM ===========================================================
REM  Step 1: launch Chrome with the remote debugging port open.
REM  The app (step 2) attaches to this Chrome over CDP.
REM
REM  NOTE: keep this file pure ASCII. Japanese text inside a .bat
REM  breaks depending on the console code page. Japanese guidance
REM  belongs in "README.txt" instead.
REM ===========================================================

REM Resolve everything relative to this file, never the current directory.
pushd "%~dp0"

REM ---- Locate chrome.exe -------------------------------------
set "CHROME="

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if not defined CHROME (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') do set "CHROME=%%B"
)
if not defined CHROME (
    for /f "tokens=2*" %%A in ('reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') do set "CHROME=%%B"
)

if not defined CHROME goto :NO_CHROME
if not exist "%CHROME%" goto :NO_CHROME

REM ---- Locate the URL list -----------------------------------
REM urls.txt ships with the folder and only holds public login pages,
REM so there is nothing for the user to fill in. Logging in and searching
REM for the property is done by hand in the Chrome window this opens.
set "URLFILE=urls.txt"

if not exist "%URLFILE%" (
    echo ===============================================================
    echo  ERROR: urls.txt was not found.
    echo.
    echo  It should sit next to this file. If you received this folder
    echo  as a zip, extract it again and keep every file together.
    echo.
    echo  Folder: %CD%
    echo ===============================================================
    popd
    pause
    exit /b 1
)

REM Strip a UTF-8 BOM if Notepad saved one. A BOM would be glued onto the
REM first URL and Chrome would open a broken address.
powershell -NoProfile -Command "$p='%URLFILE%'; $b=[IO.File]::ReadAllBytes($p); if($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF){[IO.File]::WriteAllBytes($p,$b[3..($b.Length-1)])}" 2>nul

REM ---- Build the URL argument list ---------------------------
setlocal EnableDelayedExpansion
set URLS=
for /f "usebackq tokens=* delims=" %%U in ("%URLFILE%") do (
    set "line=%%U"
    if not "!line!"=="" if not "!line:~0,1!"=="#" set URLS=!URLS! "%%U"
)

echo Chrome   : %CHROME%
echo URL list : %URLFILE%
echo Starting Chrome on debug port 9222 ...

REM A dedicated profile directory is required: without it Chrome would reuse
REM an already running instance and silently ignore the debugging port.
set "PROFILE_DIR=%LOCALAPPDATA%\syayuu_nyuuryoku_chrome"
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE_DIR%" !URLS!
endlocal

popd
exit /b 0

:NO_CHROME
echo ===============================================================
echo  ERROR: Google Chrome was not found on this PC.
echo.
echo  Searched:
echo    %ProgramFiles%\Google\Chrome\Application\chrome.exe
echo    %ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
echo    %LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
echo    registry App Paths (HKLM / HKCU)
echo.
echo  This tool drives Chrome, so Chrome must be installed.
echo  Microsoft Edge cannot be used.
echo ===============================================================
popd
pause
exit /b 1
