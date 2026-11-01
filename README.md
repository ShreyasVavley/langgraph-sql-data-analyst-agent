# DataPulse AI: Natural Language SQL Data Analyst Agent

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-indigo.svg)](https://github.com/langchain-ai/langgraph)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/Tests-14%2F14%20Passing-emerald.svg)]()
[![Deploy to Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/deploy?repository=ShreyasVavley/langgraph-sql-data-analyst-agent&branch=main&mainModule=app.py)
[![License](https://img.shields.io/badge/License-MIT-slate.svg)]()

A production-ready, highly polished **Natural Language to SQL Data Analyst Agent** built with **Python**, **LangGraph**, **Pandas**, **Plotly**, and **Streamlit**. Engineered specifically for high-stakes live demonstrations to academic evaluators and enterprise clients. Features a crisp **executive-clean light mode UI** (`#F8FAFC`, slate typography, indigo accents), transparent multi-step reasoning, and an autonomous **self-correction loop** that dynamically intercepts SQL syntax/runtime errors and heals them using LangGraph state transitions.

---

## 🏛️ System Architecture

```text
               ┌────────────────────────┐
               │    User Inquiry (NL)   │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │ 1. generate_query      │◄── (Database Schema DDL)
               │    (Pydantic Schema)   │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │ 2. execute_query       │
               │    (SQLite Execution)  │
               └─────┬────────────┬─────┘
                     │            │
       [Runtime Error]            [Success]
       & retry < 3   │            │
                     ▼            │
         ┌───────────────────┐    │
         │ 3. self_correct   │    │
         │    (Traceback Fix)│    │
         └───────────┬───────┘    │
                     │            │
                     ▼ (Loop Back)│
               (execute_query)    │
                                  ▼
               ┌────────────────────────┐
               │ 4. synthesize_and_vis  │
               │    (Plotly + Narrative)│
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │  Executive Dashboard   │
               │  - Summary Narrative   │
               │  - KPI Metric Cards    │
               │  - Interactive Chart   │
               │  - Executed SQL        │
               │  - Raw Table Preview   │
               │  - Evaluator Sandbox   │
               └────────────────────────┘
```

---

## 🚀 All Phases Completed

### Phase 1: Database & Relational Foundation (`database.py`)
- Normalized 5-table enterprise relational database (`categories`, `customers`, `products`, `orders`, `order_items`).
- Deterministic synthetic dataset featuring 60 customers, 25 products, 160 orders, and 450 order items across 2024–2026.
- SQLite query optimization with indices on high-cardinality foreign keys and dates.
- High-level business intelligence metrics aggregator (`total_revenue`, `completed_orders`, `total_customers`, `avg_order_value`).
- Safe execution wrapper enforcing read-only `SELECT` queries with sub-millisecond execution benchmarking.

### Phase 2: LangGraph State Machine & Multi-Model Engine (`agent.py`)
- Pydantic v2 schemas: `SQLQueryOutput`, `SQLCorrectionOutput`, and `VisualizationInsightOutput` with embedded `KPIMetric` cards.
- Multi-provider flexibility: Works with direct OpenAI keys, custom local endpoints (Ollama, vLLM, Groq), or the deterministic offline demonstration engine.
- Self-correction loop: Intercepts SQLite errors, extracts the stack trace, feeds it back into the LLM with the active schema, increments the retry counter, and re-executes.
- Visualization inference engine: Dynamically configures **Bar**, **Line**, **Area**, **Scatter**, or **Pie** charts based on result dimensionality.

### Phase 3: Comprehensive Test Suite & Benchmarks (`tests/`)
- 14 automated unit and integration tests covering:
  - Table existence and foreign key consistency.
  - Read-only security guards (blocking destructive operations like `DROP` or `DELETE`).
  - Pydantic schema validation and code sanitization.
  - LangGraph node execution and routing edge logic.
  - End-to-end self-correction recovery verification (confirming automatic recovery on intentional syntax errors).
- Run anytime with: `python -m pytest tests -v` (100% pass rate).

### Phase 4: Executive Streamlit UI/UX Polish (`app.py`)
- Executive-clean light mode layout (`#F8FAFC`, slate `#0F172A`, `#334155`, soft borders `#E2E8F0`, indigo/blue `#4F46E5` / `#2563EB`).
- Top Bar KPI summary displaying live enterprise figures ($5.32M revenue, 155 orders, $34.3K AOV).
- Interactive Database Schema Inspector with row count badges and live 3-row sample table previews.
- Collapsible **Agent Thought Process Expander**: Exposes real-time agent progression (SQL generation rationale, execution latency in milliseconds, self-correction diagnoses, and visual synthesis decisions).
- 4-Tab Executive Results Dashboard:
  - **Tab 1: 📊 Executive Briefing & Visualization**: Actionable takeaways, query KPIs, and interactive Plotly chart with light mode styling.
  - **Tab 2: 📋 Data Table & Export**: Tabular data preview with one-click CSV and JSON downloads.
  - **Tab 3: 💻 Executed SQL & Query Plan**: Syntax-highlighted SQL with attempt counters and duration metrics.
  - **Tab 4: 🛠️ Direct SQL Sandbox**: Allows academic evaluators to type their own raw SQL queries directly into the SQLite database to cross-check results.

### Phase 5: Containerization & Launcher Artifacts
- `Dockerfile` & `docker-compose.yml` for zero-configuration container deployment.
- `run_demo.bat` (Windows 1-click launcher).
- `run_demo.sh` (Linux/macOS 1-click launcher).

---

## 📁 Repository Structure

```text
cool-hopper/
├── app.py                  # Main Streamlit executive user interface
├── agent.py                # LangGraph state machine & self-correction loop
├── database.py             # SQLite database engine, DDL generator & mock data
├── requirements.txt        # Exact production dependencies
├── Dockerfile              # Container deployment recipe
├── docker-compose.yml      # Multi-platform container configuration
├── run_demo.bat            # Windows 1-click execution launcher
├── run_demo.sh             # Linux/macOS 1-click execution launcher
├── .env.example            # API configuration template
├── tests/
│   ├── conftest.py         # Pytest environment configuration
│   ├── test_database.py    # Database schema, seeding & security tests
│   ├── test_agent.py       # Pydantic schemas, node functions & graph tests
│   └── test_pipeline.py    # End-to-end execution & self-correction tests
└── README.md               # Complete documentation
```

---

## ⚡ Quickstart

### Option A: 1-Click Launchers
- **Windows:** Double-click [`run_demo.bat`](file:///c:/Users/Hi/Documents/antigravity/cool-hopper/run_demo.bat)
- **macOS / Linux:** Run `chmod +x run_demo.sh && ./run_demo.sh`

### Option B: Manual Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run test suite
python -m pytest tests -v

# 3. Launch Streamlit
streamlit run app.py
```

### Option C: Docker Deployment
```bash
docker-compose up --build
```
Navigate to `http://localhost:8501`.

---

## 🧪 Demonstration Guide for Evaluators

1. **Standard Inquiries:** Click any prompt in the left sidebar (e.g., *"What are the top 5 revenue generating products?"* or *"Show monthly sales trends by customer segment"*).
2. **Witness Self-Correction in Action:** Click the **"🧪 Test Self-Correction Loop"** button in the sidebar.
   - Open the **Agent Reasoning & State Trajectory** expander.
   - Note how Step 1 generated an intentional schema mismatch (`client_records`).
   - Note how Step 2 captured the SQLite execution error.
   - Note how Step 3 triggered the self-correction node, diagnosed the root cause, and synthesized the fixed SQL.
   - Note how Step 2 re-executed cleanly and Step 4 generated the visualization and KPIs.
3. **Cross-Check with the Sandbox:** Switch to **Tab 4 (Direct SQL Sandbox)** and execute raw queries against `analytics.db` to verify the agent's calculations independently.
