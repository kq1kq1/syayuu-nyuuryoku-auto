@echo off
set PYTHONW=C:\Users\user\AppData\Local\Programs\Python\Python313\pythonw.exe
pushd "%~dp0"
start "" "%PYTHONW%" main.py
popd
