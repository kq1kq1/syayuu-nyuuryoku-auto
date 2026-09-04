@echo off
REM ===========================================================
REM  Step 2: launch the input tool (main.py).
REM
REM  The same file works in two situations:
REM    - distributed folder : uses the bundled python\ runtime
REM    - developer PC       : uses the system Python via the py launcher
REM
REM  NOTE: keep this file pure ASCII. Japanese text inside a .bat
REM  breaks depending on the console code page. Japanese guidance
REM  belongs in "README.txt" instead.
REM ===========================================================

REM Resolve everything relative to this file, never the current directory.
pushd "%~dp0"

set "PY_GUI="
set "PY_CONSOLE="
set "PY_KIND="

REM ---- 1) bundled runtime (what gets distributed) ------------
if exist "python\pythonw.exe" (
    set "PY_GUI=python\pythonw.exe"
    set "PY_CONSOLE=python\python.exe"
    set "PY_KIND=bundled runtime (python\)"
    goto :FOUND
)

REM ---- 2) py launcher, installed by python.org installers ----
where pyw.exe >nul 2>&1
if not errorlevel 1 (
    set "PY_GUI=pyw.exe -3"
    set "PY_CONSOLE=py.exe -3"
    set "PY_KIND=system Python via py launcher"
    goto :FOUND
)

REM ---- 3) plain pythonw.exe on PATH --------------------------
where pythonw.exe >nul 2>&1
if not errorlevel 1 (
    set "PY_GUI=pythonw.exe"
    set "PY_CONSOLE=python.exe"
    set "PY_KIND=pythonw.exe on PATH"
    goto :FOUND
)

echo ===============================================================
echo  ERROR: no Python runtime found.
echo.
echo  Looked for:
echo    1. python\pythonw.exe  (bundled runtime, should ship with this folder)
echo    2. pyw.exe             (py launcher)
echo    3. pythonw.exe         (on PATH)
echo.
echo  If you received this folder as a zip, the python\ folder is
echo  missing - the zip was probably extracted incompletely.
echo  Extract the zip again and keep every file together.
echo ===============================================================
popd
pause
exit /b 1

:FOUND
echo Python: %PY_KIND%

REM ---- Preflight -------------------------------------------------
REM pythonw.exe has no console, so a crash at startup would be totally
REM invisible - the user double-clicks and nothing happens. main.py also
REM cannot log it, because the import failure happens before its
REM try/except. So check the imports with the console interpreter first.
REM
REM Creating a real Tk window matters: "import tkinter" is pure Python and
REM succeeds even when the tcl/ script directory is missing. Only building a
REM window proves Tcl/Tk actually loads. withdraw() keeps it off screen.
%PY_CONSOLE% -c "import tkinter, tkinter.ttk, tkinter.filedialog, openpyxl, playwright.sync_api; r = tkinter.Tk(); r.withdraw(); r.destroy()"
if errorlevel 1 (
    echo.
    echo ===============================================================
    echo  ERROR: this Python runtime is missing required modules.
    echo  The error printed just above tells you which one.
    echo.
    echo  tkinter missing
    echo    - the bundled python\ folder was built incorrectly,
    echo      or a bare "embeddable" Python is being used.
    echo      Ask for a freshly built zip.
    echo  playwright / openpyxl missing
    echo    - the libraries were never installed into this runtime.
    echo ===============================================================
    popd
    pause
    exit /b 1
)

start "" %PY_GUI% main.py
popd
exit /b 0
