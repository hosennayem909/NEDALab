@echo off
cd /d "%~dp0backend"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Backend starting on port 8000...
echo Press Ctrl+C to stop.
echo.
uvicorn main:app --reload --port 8000
pause