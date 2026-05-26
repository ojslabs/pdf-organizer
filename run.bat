@echo off
REM One-command launcher for Windows: sets up a virtual environment,
REM installs dependencies, and starts the PDF Organizer.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is required but was not found. Install it from https://python.org and try again.
  pause
  exit /b 1
)

if not exist .venv (
  echo Setting up (first run only)...
  python -m venv .venv
)

.venv\Scripts\python -m pip install --quiet --upgrade pip
.venv\Scripts\python -m pip install --quiet -r requirements.txt

echo.
echo PDF Organizer is starting at http://localhost:8080
echo Press Ctrl+C to stop. Your work auto-saves.
echo.
.venv\Scripts\python app.py
