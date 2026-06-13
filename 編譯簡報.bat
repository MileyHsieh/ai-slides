@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ===================================================
echo            AI Slides : Build + Auto Upload
echo ===================================================
echo.
echo [1/2] Building slides (Markdown -^> HTML)...
echo.

python "%~dp0build_presentation.py"
if errorlevel 1 goto build_fail

echo.
echo [2/2] Uploading to GitHub...
echo.

git add -A
git diff --cached --quiet
if errorlevel 1 goto do_push
echo No changes. Nothing to upload.
goto done

:do_push
git commit -m "Update slides %date% %time%"
git push origin main
if errorlevel 1 goto push_fail
echo.
echo Uploaded to GitHub successfully.
goto done

:build_fail
echo.
echo [ERROR] Build failed. Upload aborted. See messages above.
echo.
pause
exit /b 1

:push_fail
echo.
echo [ERROR] Upload failed. Check network or re-login GitHub.
goto done

:done
echo.
echo ===================================================
echo All done!
echo ===================================================
pause
