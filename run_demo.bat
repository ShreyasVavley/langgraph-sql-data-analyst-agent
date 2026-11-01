@echo off
echo =============================================================================
echo   DataPulse AI - Natural Language SQL Analyst Agent (Live Demo Launcher)
echo =============================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH. Please install Python 3.10 or higher.
    pause
    exit /b 1
)

echo [1/3] Checking environment & installing dependencies...
pip install -r requirements.txt >nul 2>&1

echo [2/3] Running automated unit and integration tests...
python -m pytest tests -q
if %errorlevel% neq 0 (
    echo [WARNING] Some tests encountered issues. Proceeding to launch app...
)

echo.
echo [3/3] Launching Streamlit Executive UI on http://localhost:8501 ...
streamlit run app.py

pause
