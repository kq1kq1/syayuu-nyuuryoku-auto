@echo off
chcp 65001 > nul
echo ========================================
echo  exe ファイルのビルド
echo ========================================
echo.

pip install pyinstaller > nul 2>&1

echo ビルド中（数分かかることがあります）...

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "社有入力bot" ^
  --add-data "automation;automation" ^
  --add-data "config;config" ^
  --hidden-import playwright ^
  --hidden-import playwright.sync_api ^
  --hidden-import openpyxl ^
  main.py

if errorlevel 1 (
    echo ビルドに失敗しました。
    pause
    exit /b 1
)

echo.
echo ========================================
echo  ビルド完了！
echo  dist\社有入力bot.exe を配布してください
echo.
echo  配布時に同梱するもの:
echo    - 社有入力bot.exe
echo    - start_chrome.bat
echo    - 物件入力テンプレート.xlsx（ツール内「テンプレート作成」で生成）
echo ========================================
pause
