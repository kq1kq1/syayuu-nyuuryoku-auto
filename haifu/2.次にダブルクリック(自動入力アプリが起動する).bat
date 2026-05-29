@echo off
chcp 65001 > nul
pushd "%~dp0"

if not exist "python\pythonw.exe" (
    echo セットアップが完了していません。
    echo 「【最初だけ】セットアップ.bat」を先に実行してください。
    pause
    exit /b 1
)

start "" "python\pythonw.exe" main.py
popd
