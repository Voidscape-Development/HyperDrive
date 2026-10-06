@echo off
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
uv run --frozen --no-dev main.py
