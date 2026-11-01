"""
app.py
=============================================================================
Streamlit Web Application for the Natural Language SQL Data Analyst Agent.
Features:
- Dynamic Multi-Database Connections (SQLite, Uploaded .db, PostgreSQL, MySQL)
- Active engine stored in st.session_state & inspected dynamically via SQLAlchemy
- Crisp executive-clean light mode UI (#F8FAFC, slate typography, indigo accents)
- High-level business KPI summary bar (adapts to e-commerce or custom DBs)
- Interactive database schema & data preview explorer in sidebar
- Categorized prompt library & one-click Self-Correction demonstration
- Collapsible Agent Thought Process Expander tracking LangGraph state transitions
- Multi-tab executive results: Narrative Insights, Interactive Plotly Visualizations,
  Tabular Data with CSV/JSON exports, Verified SQL Code, and an Evaluator SQL Sandbox
=============================================================================
"""

import os
import json
import time
import traceback
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import database
import agent


# =============================================================================
# 1. Page Configuration & Custom CSS Injection
# =============================================================================

st.set_page_config(
    page_title="DataPulse AI | Natural Language SQL Analyst",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

CUSTOM_CSS = """
<style>
/* ---------------------------------------------------------
   Executive Light Mode Theme Variables & Base Styles
--------------------------------------------------------- */
:root {
    --bg-main: #F8FAFC;
    --bg-card: #FFFFFF;
    --border-color: #E2E8F0;
    --border-focus: #6366F1;
    --text-primary: #0F172A;
    --text-secondary: #334155;
    --text-muted: #64748B;
    --indigo-primary: #4F46E5;
    --indigo-hover: #4338CA;
    --blue-accent: #2563EB;
    --success-bg: #ECFDF5;
    --success-text: #065F46;
    --success-border: #A7F3D0;
    --warning-bg: #FFFBEB;
    --warning-text: #92400E;
    --warning-border: #FDE68A;
    --error-bg: #FEF2F2;
    --error-text: #991B1B;
    --error-border: #FECACA;
}

/* Base Body & App Container */
.stApp {
    background-color: var(--bg-main);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Main Content Padding */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 3.5rem;
    max-width: 1320px;
}

/* Sidebar Styling */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid var(--border-color);
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}

/* Executive Cards */
.exec-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05);
}

.exec-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #F1F5F9;
}

/* KPI Stat Cards */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 1rem;
    margin-bottom: 1.25rem;
}
.kpi-card {
    background-color: #FFFFFF;
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 0.9rem 1.15rem;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    border-left: 3px solid var(--indigo-primary);
}
.kpi-label {
    font-size: 0.76rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}
.kpi-value {
    font-size: 1.35rem;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.2;
}

/* Badge Pills */
.pill-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.65rem;
    border-radius: 9999px;
    font-size: 0.76rem;
    font-weight: 600;
    line-height: 1;
}
.pill-indigo {
    background-color: #EEF2FF;
    color: #4338CA;
    border: 1px solid #C7D2FE;
}
.pill-emerald {
    background-color: var(--success-bg);
    color: var(--success-text);
    border: 1px solid var(--success-border);
}
.pill-amber {
    background-color: var(--warning-bg);
    color: var(--warning-text);
    border: 1px solid var(--warning-border);
}
.pill-rose {
    background-color: var(--error-bg);
    color: var(--error-text);
    border: 1px solid var(--error-border);
}

/* Thought Process Step Container */
.thought-step-card {
    background-color: #FFFFFF;
    border-left: 4px solid var(--indigo-primary);
    border-top: 1px solid var(--border-color);
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 0.85rem 1.1rem;
    margin-bottom: 0.85rem;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.thought-step-card.error {
    border-left-color: #EF4444;
    background-color: #FFF5F5;
}
.thought-step-card.corrected {
    border-left-color: #F59E0B;
    background-color: #FFFDF5;
}
.thought-step-card.success {
    border-left-color: #10B981;
}

/* Main content Primary Action Buttons */
section.main div.stButton > button,
div[data-testid="stMainBlockContainer"] div.stButton > button {
    background: linear-gradient(135deg, #4F46E5 0%, #3B82F6 100%) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.55rem 1.25rem !important;
    box-shadow: 0 2px 4px rgba(79, 70, 229, 0.2) !important;
    transition: all 0.2s ease-in-out !important;
}
section.main div.stButton > button:hover,
div[data-testid="stMainBlockContainer"] div.stButton > button:hover {
    background: linear-gradient(135deg, #4338CA 0%, #2563EB 100%) !important;
    box-shadow: 0 4px 8px rgba(79, 70, 229, 0.3) !important;
    transform: translateY(-1px) !important;
}

/* Sidebar Prompt & Navigation Buttons */
section[data-testid="stSidebar"] div.stButton > button {
    background: #F1F5F9 !important;
    background-color: #F1F5F9 !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 0.8rem !important;
    text-align: left !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    transition: all 0.15s ease-in-out !important;
    justify-content: flex-start !important;
    line-height: 1.35 !important;
}

section[data-testid="stSidebar"] div.stButton > button p {
    color: inherit !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    text-align: left !important;
}

section[data-testid="stSidebar"] div.stButton > button:hover {
    background: #EEF2FF !important;
    background-color: #EEF2FF !important;
    color: #2563EB !important;
    border-color: #3B82F6 !important;
    box-shadow: 0 2px 6px rgba(37, 99, 235, 0.12) !important;
    transform: translateY(-1px) !important;
}

section[data-testid="stSidebar"] div.stButton > button:active {
    background: #E0E7FF !important;
    background-color: #E0E7FF !important;
    color: #1D4ED8 !important;
    border-color: #2563EB !important;
    transform: translateY(0px) !important;
}

/* Secondary & Download Action Buttons */
div.stDownloadButton > button,
div.stButton > button[kind="secondary"] {
    background-color: #F8FAFC !important;
    color: #334155 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease-in-out !important;
}
div.stDownloadButton > button:hover,
div.stButton > button[kind="secondary"]:hover {
    background-color: #EEF2FF !important;
    color: #2563EB !important;
    border-color: #3B82F6 !important;
}

/* Streamlit Expander styling */
.streamlit-expanderHeader {
    background-color: #FFFFFF !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
}

/* Code & Pre Blocks */
pre, code {
    font-family: "JetBrains Mono", "SF Mono", Consolas, Menlo, monospace !important;
}

/* Tabs Styling */
button[data-baseweb="tab"] {
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.2rem !important;
}

/* Dataframe Borders */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: #FFFFFF;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =============================================================================
# 2. Application State Management
# =============================================================================

if "db_engine" not in st.session_state:
    st.session_state.db_engine = database.get_default_engine()
    st.session_state.db_type = "SQLite (Default)"
    st.session_state.db_label = "Built-in E-Commerce (analytics.db)"

if "last_query" not in st.session_state:
    st.session_state.last_query = ""

if "agent_output" not in st.session_state:
    st.session_state.agent_output = None

if "query_input_val" not in st.session_state:
    st.session_state.query_input_val = "What are the top 5 revenue generating products?"

if "query_history" not in st.session_state:
    st.session_state.query_history = []


def set_query(query_text: str):
    """Callback to set query input and trigger immediate analysis."""
    st.session_state.query_input_val = query_text
    st.session_state.auto_submit = True


# =============================================================================
# 3. Sidebar: Multi-Database Connections, Settings & Dynamic Schema Explorer
# =============================================================================

with st.sidebar:
    # App Branding
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
        <div style="background: linear-gradient(135deg, #4F46E5, #3B82F6); width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.3rem; font-weight: bold;">⚡</div>
        <div>
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: #0F172A;">DataPulse AI</h3>
            <span style="font-size: 0.75rem; color: #64748B; font-weight: 500;">Multi-DB LangGraph Analyst</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Active Database Indicator Badge
    curr_dialect = st.session_state.db_engine.dialect.name.upper()
    st.markdown(f"""
    <div style="margin-top: 0.4rem; margin-bottom: 0.6rem;">
        <span class="pill-badge pill-emerald">● Active: {curr_dialect}</span>
        <div style="font-size: 0.75rem; color: #64748B; margin-top: 0.25rem;">{st.session_state.db_label}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)

    # 1. Multi-Database Connection Manager
    with st.expander("🗄️ Database Connection Manager", expanded=False):
        db_source = st.selectbox(
            "Connection Mode",
            [
                "Default Demo DB (analytics.db)",
                "Upload Custom SQLite File (.db)",
                "PostgreSQL",
                "MySQL",
                "Custom SQLAlchemy URI"
            ],
            index=0
        )

        if db_source == "Default Demo DB (analytics.db)":
            st.caption("Realistic synthetic enterprise dataset (60 customers, 25 products, 160 orders).")
            if st.button("🔄 Reset to Default Demo DB", key="btn_reset_default_db", use_container_width=True):
                st.session_state.db_engine = database.get_default_engine()
                st.session_state.db_type = "SQLite (Default)"
                st.session_state.db_label = "Built-in E-Commerce (analytics.db)"
                st.session_state.agent_output = None
                st.success("Connected to default analytics.db!")
                st.rerun()

        elif db_source == "Upload Custom SQLite File (.db)":
            st.caption("Upload any SQLite database file (.db, .sqlite, .sqlite3).")
            uploaded_db = st.file_uploader(
                "Choose an SQLite file",
                type=["db", "sqlite", "sqlite3"],
                key="uploader_sqlite_file"
            )
            if uploaded_db is not None:
                os.makedirs("uploads", exist_ok=True)
                save_path = os.path.join("uploads", uploaded_db.name)
                with open(save_path, "wb") as f:
                    f.write(uploaded_db.getbuffer())

                if st.button(f"⚡ Connect to {uploaded_db.name}", key="btn_connect_uploaded", use_container_width=True):
                    try:
                        new_engine = database.create_custom_engine(f"sqlite:///{os.path.abspath(save_path)}")
                        ok, msg = database.test_engine_connection(new_engine)
                        if ok:
                            st.session_state.db_engine = new_engine
                            st.session_state.db_type = "SQLite (Uploaded)"
                            st.session_state.db_label = f"Uploaded: {uploaded_db.name}"
                            st.session_state.agent_output = None
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(f"Connection test failed: {msg}")
                    except Exception as err:
                        st.error(f"Error loading uploaded database: {str(err)}")

        elif db_source == "PostgreSQL":
            st.caption("Connect to a PostgreSQL database instance.")
            pg_host = st.text_input("Host", value="localhost", key="pg_host")
            pg_port = st.number_input("Port", value=5432, step=1, key="pg_port")
            pg_db = st.text_input("Database Name", value="analytics", key="pg_db")
            pg_user = st.text_input("Username", value="postgres", key="pg_user")
            pg_pass = st.text_input("Password", type="password", key="pg_pass")

            if st.button("🐘 Connect to PostgreSQL", key="btn_connect_pg", use_container_width=True):
                try:
                    uri = database.build_connection_uri("postgresql", pg_host, int(pg_port), pg_db, pg_user, pg_pass)
                    new_engine = database.create_custom_engine(uri)
                    ok, msg = database.test_engine_connection(new_engine)
                    if ok:
                        st.session_state.db_engine = new_engine
                        st.session_state.db_type = "PostgreSQL"
                        st.session_state.db_label = f"PostgreSQL ({pg_db}@{pg_host})"
                        st.session_state.agent_output = None
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(f"Connection failed: {msg}")
                except Exception as err:
                    st.error(f"Failed to create PostgreSQL engine: {str(err)}")

        elif db_source == "MySQL":
            st.caption("Connect to a MySQL database instance.")
            my_host = st.text_input("Host", value="localhost", key="my_host")
            my_port = st.number_input("Port", value=3306, step=1, key="my_port")
            my_db = st.text_input("Database Name", value="analytics", key="my_db")
            my_user = st.text_input("Username", value="root", key="my_user")
            my_pass = st.text_input("Password", type="password", key="my_pass")

            if st.button("🐬 Connect to MySQL", key="btn_connect_mysql", use_container_width=True):
                try:
                    uri = database.build_connection_uri("mysql", my_host, int(my_port), my_db, my_user, my_pass)
                    new_engine = database.create_custom_engine(uri)
                    ok, msg = database.test_engine_connection(new_engine)
                    if ok:
                        st.session_state.db_engine = new_engine
                        st.session_state.db_type = "MySQL"
                        st.session_state.db_label = f"MySQL ({my_db}@{my_host})"
                        st.session_state.agent_output = None
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(f"Connection failed: {msg}")
                except Exception as err:
                    st.error(f"Failed to create MySQL engine: {str(err)}")

        elif db_source == "Custom SQLAlchemy URI":
            st.caption("Direct SQLAlchemy connection string.")
            custom_uri = st.text_input(
                "Connection URI",
                value="sqlite:///analytics.db",
                placeholder="postgresql+psycopg2://user:pass@host:5432/dbname",
                key="custom_uri_input"
            )
            if st.button("🔗 Connect via URI", key="btn_connect_uri", use_container_width=True):
                try:
                    new_engine = database.create_custom_engine(custom_uri.strip())
                    ok, msg = database.test_engine_connection(new_engine)
                    if ok:
                        st.session_state.db_engine = new_engine
                        st.session_state.db_type = new_engine.dialect.name.upper()
                        st.session_state.db_label = f"Custom URI ({new_engine.dialect.name})"
                        st.session_state.agent_output = None
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(f"Connection failed: {msg}")
                except Exception as err:
                    st.error(f"Engine creation failed: {str(err)}")

    # 2. LLM & Inference Settings
    with st.expander("⚙️ LLM & Engine Settings", expanded=False):
        provider = st.selectbox(
            "Inference Engine",
            ["OpenAI / Direct Key", "Custom Endpoint (Ollama / vLLM / Groq)", "Deterministic Offline Engine"],
            index=0
        )

        api_key_input = ""
        base_url_input = None
        selected_model = "gpt-4o-mini"

        if provider == "OpenAI / Direct Key":
            default_key = os.getenv("OPENAI_API_KEY", "")
            if not default_key:
                try:
                    default_key = st.secrets.get("OPENAI_API_KEY", "")
                except Exception:
                    pass

            api_key_input = st.text_input(
                "OpenAI API Key",
                type="password",
                value=default_key,
                help="Key used for Pydantic structured output generation."
            )
            selected_model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], index=0)
            if api_key_input:
                st.markdown('<span class="pill-badge pill-emerald">● Live OpenAI Connected</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="pill-badge pill-amber">⚡ Deterministic Mode Active</span>', unsafe_allow_html=True)

        elif provider == "Custom Endpoint (Ollama / vLLM / Groq)":
            base_url_input = st.text_input("Base URL", value="http://localhost:11434/v1")
            api_key_input = st.text_input("API Key (Optional)", type="password", value="ollama")
            selected_model = st.text_input("Model Identifier", value="llama3.1:latest")
            st.markdown('<span class="pill-badge pill-indigo">● Custom Endpoint Configured</span>', unsafe_allow_html=True)

        else:
            st.markdown('<span class="pill-badge pill-emerald">● Built-in Deterministic Engine</span>', unsafe_allow_html=True)
            st.caption("Operates offline using the analytical benchmark catalog.")

    # 3. Dynamic Database Schema Explorer
    st.markdown("<p style='font-size: 0.82rem; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; margin: 0.75rem 0 0.35rem 0;'>Inspected Database Schema</p>", unsafe_allow_html=True)

    active_meta = database.get_engine_schema_metadata(st.session_state.db_engine)
    total_db_rows = sum(m["row_count"] for m in active_meta.values() if m["row_count"] > 0)

    st.markdown(f"""
    <div style="font-size: 0.78rem; color: #64748B; margin-bottom: 0.6rem;">
        Dialect: <code>{curr_dialect}</code> &bull; <strong>{len(active_meta)}</strong> tables &bull; <strong>{total_db_rows:,}</strong> total rows
    </div>
    """, unsafe_allow_html=True)

    for table_name, meta in active_meta.items():
        row_label = f"{meta['row_count']} rows" if meta['row_count'] >= 0 else "live"
        with st.expander(f"📁 {table_name} ({row_label})", expanded=False):
            col_data = []
            for col in meta["columns"]:
                col_data.append({
                    "Column": col["name"],
                    "Type": col["type"],
                    "PK": "🔑" if col["pk"] else ""
                })
            st.dataframe(pd.DataFrame(col_data), use_container_width=True, hide_index=True)

            try:
                preview_df = database.get_engine_table_preview(st.session_state.db_engine, table_name, limit=3)
                st.caption("Sample 3 Rows:")
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
            except Exception:
                pass

    st.markdown("<hr style='margin: 0.75rem 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)

    # 4. Prompt Suggestions & Test Triggers
    st.markdown("<p style='font-size: 0.82rem; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;'>Sample Analytical Prompts</p>", unsafe_allow_html=True)

    prompts = [
        "What are the top 5 revenue generating products?",
        "Show monthly sales trends by customer segment",
        "Which region has the highest average order value?",
        "Compare profit margin percentage by category",
        "Breakdown of order volume by fulfillment status",
        "Top 10 enterprise and SMB accounts by lifetime spend"
    ]

    for p in prompts:
        if st.button(p, key=f"btn_p_{p}", use_container_width=True):
            set_query(p)

    st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
    if st.button("🧪 Test Self-Correction Loop", key="btn_test_error", use_container_width=True):
        set_query("Test self-correction: Select client_name and total sales from client_records")

    if st.session_state.query_history:
        st.markdown("<hr style='margin: 0.75rem 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 0.82rem; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;'>Recent Queries</p>", unsafe_allow_html=True)
        for h_q in reversed(st.session_state.query_history[-3:]):
            if st.button(f"⏱️ {h_q[:35]}...", key=f"hist_{h_q}", use_container_width=True):
                set_query(h_q)


# =============================================================================
# 4. Main Executive Interface & KPI Summary Bar
# =============================================================================

# Hero Banner
st.markdown(f"""
<div class="exec-card" style="border-top: 4px solid #4F46E5; background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%); margin-bottom: 1rem;">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
        <div>
            <h1 style="font-size: 1.65rem; font-weight: 800; color: #0F172A; margin: 0 0 0.35rem 0; letter-spacing: -0.02em;">
                Natural Language SQL Data Analyst Agent
            </h1>
            <p style="font-size: 0.95rem; color: #475569; margin: 0; line-height: 1.5;">
                Autonomous LangGraph multi-stage state machine with self-correction, dynamic SQLAlchemy schema grounding, and interactive Plotly visualization.
            </p>
        </div>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <span class="pill-badge pill-indigo">LangGraph 0.2</span>
            <span class="pill-badge pill-emerald">{curr_dialect} Engine</span>
            <span class="pill-badge pill-amber">Self-Correction Guard</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Executive KPI Summary Bar
db_metrics = database.get_engine_metrics(st.session_state.db_engine)

if db_metrics.get("is_ecommerce", False):
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-label">Enterprise Gross Revenue</div>
            <div class="kpi-value">${db_metrics['total_revenue']:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Completed Orders</div>
            <div class="kpi-value">{db_metrics['completed_orders']:,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Active Customer Accounts</div>
            <div class="kpi-value">{db_metrics['total_customers']}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Average Order Value (AOV)</div>
            <div class="kpi-value">${db_metrics['avg_order_value']:,.2f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-label">Connected Database Dialect</div>
            <div class="kpi-value">{db_metrics['dialect'].upper()}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Inspected User Tables</div>
            <div class="kpi-value">{db_metrics['total_tables']}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Estimated Total Rows</div>
            <div class="kpi-value">{db_metrics['total_rows']:,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Connection Mode</div>
            <div class="kpi-value" style="font-size: 1.1rem;">{st.session_state.db_type}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# Query Input Form
col_input, col_btn, col_rnd = st.columns([5, 1, 1])

with col_input:
    user_query = st.text_input(
        "Enter your business inquiry in natural language:",
        value=st.session_state.query_input_val,
        placeholder="e.g., Which product category achieved the highest net profit margin?",
        label_visibility="collapsed"
    )

with col_btn:
    run_clicked = st.button("🚀 Analyze", use_container_width=True)

with col_rnd:
    if st.button("🎲 Random", use_container_width=True):
        import random
        random_options = [
            "What are the top 5 revenue generating products?",
            "Show monthly sales trends by customer segment",
            "Which region has the highest average order value?",
            "Compare profit margin percentage by category",
            "Breakdown of order volume by fulfillment status",
            "Top 10 enterprise and SMB accounts by lifetime spend"
        ]
        set_query(random.choice(random_options))

# Determine if execution is triggered
should_run = run_clicked or st.session_state.get("auto_submit", False)
if st.session_state.get("auto_submit", False):
    st.session_state.auto_submit = False


# =============================================================================
# 5. Agent Pipeline Execution & State Propagation
# =============================================================================

if should_run and user_query.strip():
    with st.spinner(f"LangGraph agent orchestrating analysis on {curr_dialect} engine..."):
        try:
            active_key = api_key_input.strip() if api_key_input else None
            state_result = agent.run_analyst_pipeline(
                user_query=user_query.strip(),
                api_key=active_key,
                model=selected_model,
                base_url=base_url_input,
                engine=st.session_state.db_engine
            )
            st.session_state.agent_output = state_result
            st.session_state.last_query = user_query.strip()

            if user_query.strip() not in st.session_state.query_history:
                st.session_state.query_history.append(user_query.strip())

        except Exception as e:
            st.error(f"Agent execution encountered an unhandled error: {str(e)}")
            st.code(traceback.format_exc())


# =============================================================================
# 6. Render Agent Thought Process Expander (Live Reasoning & Self-Correction)
# =============================================================================

output = st.session_state.agent_output

if output:
    thought_steps = output.get("thought_steps", [])
    retry_count = output.get("retry_count", 0)
    has_self_correction = retry_count > 0

    expander_title = f"🧠 Agent Reasoning & State Trajectory ({len(thought_steps)} Steps • {curr_dialect}"
    if has_self_correction:
        expander_title += f" &bull; ⚠️ {retry_count} Self-Correction Loop{'s' if retry_count > 1 else ''} Triggered)"
    else:
        expander_title += " &bull; ✅ Flawless Execution)"

    with st.expander(expander_title, expanded=True):
        st.markdown(f"""
        <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 0.85rem;">
            Inspect each state transition in the LangGraph workflow: query formulation, execution benchmark, runtime error capture, self-correction, and visual synthesis grounded in <code>{curr_dialect}</code>.
        </div>
        """, unsafe_allow_html=True)

        for idx, step in enumerate(thought_steps):
            step_status = step.get("status", "success")
            badge_class = "pill-emerald"
            card_class = "thought-step-card success"

            if step_status == "error":
                badge_class = "pill-rose"
                card_class = "thought-step-card error"
            elif step_status in ["corrected", "warning"]:
                badge_class = "pill-amber"
                card_class = "thought-step-card corrected"

            st.markdown(f"""
            <div class="{card_class}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                    <div style="font-weight: 700; font-size: 0.92rem; color: #0F172A;">
                        {step.get('title', step.get('step'))}
                    </div>
                    <div style="display: flex; gap: 0.4rem; align-items: center;">
                        <span class="pill-badge {badge_class}">{step.get('step')}</span>
                        <span style="font-size: 0.75rem; color: #94A3B8; font-weight: 500;">{step.get('time')}</span>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: #334155; line-height: 1.5; white-space: pre-wrap;">
{step.get('detail', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if "sql" in step:
                st.markdown("<p style='font-size: 0.78rem; font-weight: 600; color: #64748B; margin: 0.2rem 0;'>Generated SQL:</p>", unsafe_allow_html=True)
                st.code(step["sql"], language="sql")

            if "error_traceback" in step:
                with st.expander("🔍 View Raw Error Traceback Intercepted by State Machine", expanded=False):
                    st.code(step["error_traceback"], language="text")

            if "tables_used" in step and step["tables_used"]:
                tables_str = ", ".join([f"`{t}`" for t in step["tables_used"]])
                st.markdown(f"<span style='font-size: 0.8rem; color: #475569;'>Referenced Schema Tables: {tables_str}</span>", unsafe_allow_html=True)


# =============================================================================
# 7. Multi-Tab Executive Results Dashboard
# =============================================================================

if output:
    st.markdown("<div style='margin-top: 1.25rem;'></div>", unsafe_allow_html=True)

    records = output.get("dataframe_result")
    df = pd.DataFrame(records) if records else pd.DataFrame()
    explanation = output.get("explanation", "Analysis completed.")
    chart_spec = output.get("chart_spec")
    kpis = output.get("kpis") or []
    sql_query = output.get("sql_query", "")

    # Tabs definition
    tab_vis, tab_data, tab_sql, tab_sandbox = st.tabs([
        "📊 Executive Briefing & Visualization",
        "📋 Data Table & Export",
        "💻 Executed SQL & Query Plan",
        "🛠️ Direct SQL Sandbox"
    ])

    # ---------------------------------------------------------
    # Tab 1: Executive Briefing & Visualization
    # ---------------------------------------------------------
    with tab_vis:
        st.markdown(f"""
        <div class="exec-card" style="border-left: 5px solid #2563EB;">
            <div class="exec-card-header">
                <span style="font-weight: 700; font-size: 1.05rem; color: #0F172A;">📊 Executive Business Insights</span>
                <span class="pill-badge pill-indigo">Automated Synthesis • {curr_dialect}</span>
            </div>
            <div style="font-size: 0.95rem; color: #334155; line-height: 1.6;">
                {explanation}
            </div>
            {f'<div style="margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #E2E8F0; font-size: 0.85rem; color: #4338CA; font-weight: 600;">🎯 Key Actionable Takeaway: {chart_spec.get("takeaway", "")}</div>' if chart_spec and chart_spec.get("takeaway") else ''}
        </div>
        """, unsafe_allow_html=True)

        if kpis:
            kpi_cols = st.columns(len(kpis))
            for i, k in enumerate(kpis):
                with kpi_cols[i]:
                    st.markdown(f"""
                    <div class="kpi-card" style="margin-bottom: 1rem;">
                        <div class="kpi-label">{k['label']}</div>
                        <div class="kpi-value" style="font-size: 1.2rem;">{k['value']}</div>
                    </div>
                    """, unsafe_allow_html=True)

        if not df.empty and chart_spec:
            c_type = chart_spec.get("chart_type", "bar")
            x_col = chart_spec.get("x")
            y_col = chart_spec.get("y")
            color_col = chart_spec.get("color")
            title = chart_spec.get("title", f"Visual Analysis ({curr_dialect})")

            if x_col not in df.columns:
                x_col = df.columns[0]
            if y_col and y_col not in df.columns:
                numeric_candidates = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                y_col = numeric_candidates[0] if numeric_candidates else (df.columns[1] if len(df.columns) > 1 else df.columns[0])

            fig = None
            color_palette = ["#4F46E5", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6", "#6366F1"]

            if c_type == "bar":
                fig = px.bar(
                    df,
                    x=x_col,
                    y=y_col,
                    color=color_col if color_col in df.columns else None,
                    title=title,
                    color_discrete_sequence=color_palette,
                    text_auto=True if len(df) <= 12 else False,
                    template="plotly_white"
                )
                fig.update_layout(xaxis_tickangle=-25 if len(df) > 5 else 0)

            elif c_type == "line":
                fig = px.line(
                    df,
                    x=x_col,
                    y=y_col,
                    color=color_col if color_col in df.columns else None,
                    markers=True,
                    title=title,
                    color_discrete_sequence=color_palette,
                    template="plotly_white"
                )

            elif c_type == "area":
                fig = px.area(
                    df,
                    x=x_col,
                    y=y_col,
                    color=color_col if color_col in df.columns else None,
                    title=title,
                    color_discrete_sequence=color_palette,
                    template="plotly_white"
                )

            elif c_type == "scatter":
                fig = px.scatter(
                    df,
                    x=x_col,
                    y=y_col,
                    color=color_col if color_col in df.columns else None,
                    size=y_col if pd.api.types.is_numeric_dtype(df[y_col]) else None,
                    title=title,
                    color_discrete_sequence=color_palette,
                    template="plotly_white"
                )

            elif c_type == "pie":
                fig = px.pie(
                    df,
                    names=x_col,
                    values=y_col,
                    title=title,
                    color_discrete_sequence=color_palette,
                    hole=0.4,
                    template="plotly_white"
                )

            else:
                fig = px.bar(
                    df,
                    x=x_col,
                    y=y_col,
                    title=title,
                    color_discrete_sequence=color_palette,
                    template="plotly_white"
                )

            if fig:
                fig.update_layout(
                    margin=dict(l=30, r=20, t=50, b=40),
                    font=dict(family="inherit", color="#1E293B"),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    hoverlabel=dict(bgcolor="#0F172A", font_color="#FFFFFF", font_size=12),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chart omitted: Query results do not feature multi-dimensional numeric data.")

    # ---------------------------------------------------------
    # Tab 2: Tabular Data & Export
    # ---------------------------------------------------------
    with tab_data:
        if not df.empty:
            col_t_summary, col_dl_csv, col_dl_json = st.columns([4, 1, 1])
            with col_t_summary:
                st.markdown(f"<span style='font-size: 0.88rem; color: #475569;'>Displaying <strong>{len(df)}</strong> record(s) across <strong>{len(df.columns)}</strong> column(s).</span>", unsafe_allow_html=True)
            with col_dl_csv:
                csv_data = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 CSV",
                    data=csv_data,
                    file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col_dl_json:
                json_data = df.to_json(orient="records", indent=2).encode("utf-8")
                st.download_button(
                    label="📥 JSON",
                    data=json_data,
                    file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

            st.dataframe(df, use_container_width=True)
        else:
            st.info("No rows returned from the database.")

    # ---------------------------------------------------------
    # Tab 3: Executed SQL & Query Plan
    # ---------------------------------------------------------
    with tab_sql:
        st.markdown(f"""
        <div style="font-size: 0.88rem; color: #475569; margin-bottom: 0.5rem;">
            Verified <code>{curr_dialect}</code> syntax synthesized and validated by the LangGraph state machine:
        </div>
        """, unsafe_allow_html=True)
        st.code(sql_query, language="sql")

        exec_time = output.get("execution_time_ms", 0.0)
        retries = output.get("retry_count", 0)
        st.markdown(f"""
        <div style="display: flex; gap: 0.75rem; margin-top: 0.5rem; flex-wrap: wrap;">
            <span class="pill-badge pill-indigo">⏱️ Execution Time: {exec_time} ms</span>
            <span class="pill-badge pill-emerald">🔄 Attempts: {retries + 1}</span>
            <span class="pill-badge pill-indigo">Engine: {curr_dialect}</span>
            <span class="pill-badge pill-indigo">Target: {st.session_state.db_label}</span>
        </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # Tab 4: Direct SQL Sandbox (For Evaluators)
    # ---------------------------------------------------------
    with tab_sandbox:
        st.markdown(f"""
        <div style="font-size: 0.88rem; color: #475569; margin-bottom: 0.75rem;">
            Academic evaluators may test and cross-verify direct read-only SQL queries against active <code>{curr_dialect}</code> engine:
        </div>
        """, unsafe_allow_html=True)

        sandbox_sql = st.text_area(
            f"Execute Raw {curr_dialect} Query:",
            value=sql_query,
            height=120,
            key="sandbox_sql_input"
        )
        if st.button("⚡ Execute Custom Query", key="btn_run_sandbox"):
            try:
                s_df, s_dur = database.execute_engine_query(sandbox_sql, st.session_state.db_engine)
                st.success(f"Query returned {len(s_df)} row(s) in {s_dur} ms.")
                st.dataframe(s_df, use_container_width=True)
            except Exception as sb_err:
                st.error(f"Execution Error: {str(sb_err)}")

elif not output and not should_run:
    st.markdown(f"""
    <div class="exec-card" style="text-align: center; padding: 3rem 1.5rem; margin-top: 1rem;">
        <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">⚡</div>
        <h3 style="font-size: 1.25rem; font-weight: 700; color: #0F172A; margin: 0 0 0.5rem 0;">Ready to Analyze Your Data ({curr_dialect})</h3>
        <p style="font-size: 0.9rem; color: #64748B; max-width: 600px; margin: 0 auto 1.5rem auto; line-height: 1.5;">
            Type any analytical inquiry in the box above or choose a curated executive prompt from the sidebar to observe the LangGraph agent generate queries, execute against {curr_dialect}, self-correct errors, and synthesize interactive visuals.
        </p>
        <div style="display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap;">
            <span class="pill-badge pill-indigo">Dynamic inspect(engine)</span>
            <span class="pill-badge pill-amber">Automated Retry Loop</span>
            <span class="pill-badge pill-emerald">Multi-DB Compatible</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
