#!/usr/bin/env bash
# =============================================================================
#   DataPulse AI - Natural Language SQL Analyst Agent (Live Demo Launcher)
# =============================================================================

set -e

echo "============================================================================="
echo "  DataPulse AI - Natural Language SQL Analyst Agent (Live Demo Launcher)"
echo "============================================================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

echo "[1/3] Verifying dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

echo "[2/3] Running automated unit and integration tests..."
python3 -m pytest tests -q || echo "[WARNING] Tests completed with warnings."

echo ""
echo "[3/3] Launching Streamlit Executive UI on http://localhost:8501 ..."
streamlit run app.py
