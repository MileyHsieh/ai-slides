@echo off
chcp 65001 > nul
echo ===================================================
echo               AI Presentation Compiler
echo ===================================================
echo.
echo Compiling Markdown slide deck to interactive HTML...
echo.

python "%~dp0build_presentation.py"

echo.
echo ===================================================
echo Compilation complete! Refresh index.html or deploy to GitHub.
echo ===================================================
pause
