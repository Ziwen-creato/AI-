@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] Fetching AI news...
py ai_news.py
if errorlevel 1 goto :error

echo [2/4] Fetching article details + translating...
py fetch_details.py
if errorlevel 1 goto :error

echo [3/4] Generating latest webpage...
py make_wechat.py
if errorlevel 1 goto :error

echo [4/4] Generating 5 selected AI news...
py make_top5.py
if errorlevel 1 goto :error

echo Done!
if not "%~1"=="auto" start "" "html\index.html"
if "%~1"=="auto" goto :end
pause
goto :end

:error
echo Task failed. Check the messages above.
pause

:end
endlocal
