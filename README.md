# DataPulse AI: Natural Language SQL Data Analyst Agent

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-indigo.svg)](https://github.com/langchain-ai/langgraph)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/Tests-19%2F19%20Passing-emerald.svg)]()
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

## 🚀 Engineering Phases Completed

### Phase 1: Dynamic Multi-Database Engine & Introspection (`database.py`)
- **SQLAlchemy 2.0 Engine Factory**: Seamless dynamic connection switching across SQLite, PostgreSQL, MySQL, and arbitrary connection URIs.
- **Dynamic Schema Introspection**: Direct `inspect(engine)` extraction of table schemas, column data types, nullability, primary key constraints, foreign key references, and 2 sample rows per table.
- **Schema RAG & Table Pruning**: Automatically tokenizes user inquiries and ranks/prunes large enterprise schemas (>15 tables) while preserving foreign key relational join paths to prevent prompt token bloat.
- **Production Guardrails**:
  - Read-only execution safety rejecting mutating statements (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `PRAGMA`).
  - Automatic `LIMIT 1000` query pagination clamping to prevent memory exhaustion on runaway queries.
  - Multi-threaded 15-second statement execution timeout enforcement.
- **Deterministic E-Commerce Benchmark**: Seeded 5-table SQLite database (60 customers, 25 products, 160 orders, 450 order items across 2024–2026) for zero-configuration offline evaluation.

### Phase 2: LangGraph State Machine & Self-Correction Loop (`agent.py`)
- **State Machine Topology**: Directed cyclical graph (`generate_query` ➔ `execute_query` ⮂ `self_correct` ➔ `synthesize_and_visualize` ➔ `END`).
- **Pydantic v2 Output Modeling**: Strictly typed contracts: `SQLQueryOutput`, `SQLCorrectionOutput`, and `VisualizationInsightOutput` with executive `KPIMetric` cards.
- **Autonomous Error Interception**: Catches SQL dialect and syntax failures, feeds the engine traceback and inspected DDL back to the reflection node, increments the retry counter, and repairs the SQL query (up to 3 automated recovery attempts).
- **Multi-Dialect Synthesis**: Dialect-aware SQL generation tailored to PostgreSQL (`TO_CHAR`), MySQL (`DATE_FORMAT`), or SQLite (`strftime`).
- **Dynamic Visualization Mapper**: Automatically maps tabular outputs into optimal Plotly light mode representations: **Bar**, **Line**, **Area**, **Scatter**, **Pie**, or **Table**.

### Phase 3: Comprehensive Automated Verification Suite (`tests/`)
- **19 Automated Tests** passing with 100% test coverage across database, agent, state transitions, and pipelines:
  - `test_database.py`: Table integrity, distribution checks, read-only security guardrails, schema DDL extraction, preview bounds, business KPIs, dynamic engine creation, intelligent schema pruning, query pagination clamping, and connection error handling.
  - `test_agent.py`: Pydantic schema serialization, markdown SQL block stripping, heuristic generation, individual node contracts, and LangGraph compilation.
  - `test_pipeline.py`: Clean multi-turn pipeline queries, automated self-correction loop recovery verification, conditional routing edge logic, and end-to-end custom SQLite engine execution.
- Run anytime with: `python -m pytest tests -v`.

### Phase 4: Executive Streamlit UI/UX & Multi-DB Manager (`app.py`)
- **Executive Light Mode Aesthetic**: Tailored CSS design system (`#F8FAFC` background, slate typography, subtle `#E2E8F0` borders, indigo/blue accents).
- **Interactive Database Connection Manager**:
  1. Default Seeded E-Commerce Database (offline ready).
  2. Custom SQLite `.db` File Uploader (drag-and-drop instant connection).
  3. PostgreSQL Parameter Form (Host, Port, Database, User, Password).
  4. MySQL Parameter Form (Host, Port, Database, User, Password).
  5. Direct Custom SQLAlchemy URI.
- **Adaptive KPI Summary Bar**: Dynamically toggles between commercial business metrics (Gross Revenue, Completed Orders, Customer Accounts, AOV) and structural database metrics (Total Tables, Dialect, Total Row Count).
- **Inspected Schema Explorer**: Interactive accordions detailing column data types, primary key badges (🔑), and 3-row live sample previews.
- **Collapsible Agent Thought Process Expander**: Real-time observability tracking SQL rationale, dialect targets, millisecond execution benchmarks, error tracebacks, and self-correction fixes.
- **4-Tab Executive Results Dashboard**:
  - **Tab 1: 📊 Executive Briefing & Visualization**: Actionable takeaways, query KPIs, and interactive Plotly chart.
  - **Tab 2: 📋 Data Table & Export**: Data table with one-click CSV and JSON downloads.
  - **Tab 3: 💻 Executed SQL & Query Plan**: Syntax-highlighted SQL with attempt counters and duration metrics.
  - **Tab 4: 🛠️ Direct SQL Sandbox**: Raw query sandbox allowing evaluators to verify results against the active engine directly.

### Phase 5: Containerization & 1-Click Launchers
- `Dockerfile` & `docker-compose.yml` for multi-platform container deployment.
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

### Option D: Streamlit Community Cloud (24/7 Always Active)
- Deploy with 1 click using the badge at the top of the repository.
- **Automated Keep-Alive**: An automated GitHub Actions cron workflow (`.github/workflows/keep_alive.yml`) runs every 6 hours to ping your app and prevent Streamlit Cloud from entering sleep mode.
- To configure your specific URL: In GitHub, go to **Settings > Secrets and variables > Actions** and add `STREAMLIT_APP_URL` (e.g., `https://your-subdomain.streamlit.app`).

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
