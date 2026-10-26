@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ClaudeZhCN.ps1" %*
set "CLAUDE_ZH_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %CLAUDE_ZH_EXIT%
