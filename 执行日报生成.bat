@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

call run_all.bat auto
if errorlevel 1 goto :error

echo [5/5] Publishing to GitHub Pages...
git add -f html/
git diff --cached --quiet
if not errorlevel 1 goto :push

git commit -m "Update AI daily news %date% %time%"
if errorlevel 1 goto :error

:push
git push origin main
if errorlevel 1 goto :error

if not "%~1"=="auto" start "" "https://ziwen-creato.github.io/AI-/index.html"
goto :end

:error
echo Publish failed. Check the messages above.
pause

:end
endlocal
