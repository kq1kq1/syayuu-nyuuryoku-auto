@echo off
echo ========================================
echo  Setup (Run only once)
echo ========================================
echo.

set PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe

IF NOT EXIST "%PYTHON%" (
    echo ERROR: Python not found at:
    echo %PYTHON%
    pause
    exit /b 1
)

echo Python OK: %PYTHON%
echo.

echo [1/2] Installing libraries...
"%PYTHON%" -m pip install playwright openpyxl
echo.

echo [2/2] Installing Playwright browser...
"%PYTHON%" -m playwright install chromium
echo.

echo ========================================
echo  Setup complete! Run run.bat next.
echo ========================================
pause
