@echo off
rem Installs Python and the dependencies locked in uv.lock into .venv
cd /d "%~dp0.."
uv sync --frozen --no-dev
pause
