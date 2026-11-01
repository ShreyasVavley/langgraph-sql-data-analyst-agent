"""
app.py
=============================================================================
Streamlit Web Application for the Natural Language SQL Data Analyst Agent.
Features:
- Crisp, executive-clean light mode UI (#F8FAFC, slate typography, indigo accents)
- High-level business KPI summary bar
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

/* Primary Action Buttons */
div.stButton > button:first-child {
    background: linear-gradient(135deg, #4F46E5 0%, #3B82F6 100%);
    color: #FFFFFF !important;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 0.55rem 1.25rem;
    box-shadow: 0 2px 4px rgba(79, 70, 229, 0.2);
    transition: all 0.2s ease-in-out;
}
div.stButton > button:first-child:hover {
    background: linear-gradient(135deg, #4338CA 0%, #2563EB 100%);
    box-shadow: 0 4px 8px rgba(79, 70, 229, 0.3);
    transform: translateY(-1px);
}

/* Secondary Action Buttons */
div.stButton > button[kind="secondary"] {
    background-color: #F8FAFC !important;
    color: #334155 !important;
    border: 1px solid var(--border-color) !important;
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

if "db_initialized" not in st.session_state:
    database.init_database()
    st.session_state.db_initialized = True

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
# 3. Sidebar: Configuration, Schema Inspector & Prompt Library
# =============================================================================

with st.sidebar:
    # App Branding
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
        <div style="background: linear-gradient(135deg, #4F46E5, #3B82F6); width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.3rem; font-weight: bold;">⚡</div>
        <div>
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: #0F172A;">DataPulse AI</h3>
            <span style="font-size: 0.75rem; color: #64748B; font-weight: 500;">LangGraph SQL Analyst</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 0.75rem 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)

    # 1. LLM & Endpoint Settings
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
            api_key_input = st.text_input(
                "OpenAI API Key",
                type="password",
                value=os.getenv("OPENAI_API_KEY", ""),
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
            st.caption("Operates 100% offline using the analytical benchmark catalog.")

    # 2. Executive Prompt Library
    st.markdown("<p style='font-size: 0.82rem; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; margin: 0.75rem 0 0.35rem 0;'>Executive Prompt Library</p>", unsafe_allow_html=True)

    prompt_category = st.radio(
        "Prompt Category",
        ["Revenue & Sales", "Customers", "Categories & Margins", "Operations"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if prompt_category == "Revenue & Sales":
        prompts = [
            "What are the top 5 revenue generating products?",
            "Show monthly sales trends by customer segment",
            "Top 10 enterprise and SMB accounts by lifetime spend"
        ]
    elif prompt_category == "Customers":
        prompts = [
            "Which region has the highest average order value?",
            "Breakdown of customer signups across segments",
            "Top 10 enterprise and SMB accounts by lifetime spend"
        ]
    elif prompt_category == "Categories & Margins":
        prompts = [
            "Compare profit margin percentage by category",
            "What are the top 5 revenue generating products?"
        ]
    else:
        prompts = [
            "Breakdown of order volume by fulfillment status",
            "Transaction volume by payment method"
        ]

    for p in prompts:
        if st.button(p, key=f"btn_p_{p}", use_container_width=True):
            set_query(p)

    # 3. Intentional Self-Correction Demonstration Button
    st.markdown("<div style='margin-top: 0.65rem;'></div>", unsafe_allow_html=True)
    if st.button("🧪 Test Self-Correction Loop", key="btn_test_error", use_container_width=True):
        set_query("Test self-correction: Select client_name and total sales from client_records")

    st.markdown("<hr style='margin: 1rem 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)

    # 4. Active Database Schema Explorer with Row Previews
    st.markdown("<p style='font-size: 0.82rem; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;'>Active SQLite Schema</p>", unsafe_allow_html=True)

    schema_meta = database.get_schema_metadata()
    total_records = sum(info["row_count"] for info in schema_meta.values())

    st.markdown(f"""
    <div style="font-size: 0.78rem; color: #64748B; margin-bottom: 0.6rem;">
        Database: <code>analytics.db</code> &bull; <strong>{len(schema_meta)}</strong> tables &bull; <strong>{total_records:,}</strong> total rows
    </div>
    """, unsafe_allow_html=True)

    for table_name, meta in schema_meta.items():
        with st.expander(f"📁 {table_name} ({meta['row_count']} rows)", expanded=False):
            col_data = []
            for col in meta["columns"]:
                col_data.append({
                    "Column": col["name"],
                    "Type": col["type"],
                    "PK": "🔑" if col["pk"] else ""
                })
            st.dataframe(pd.DataFrame(col_data), use_container_width=True, hide_index=True)

            # Table Preview inside expander
            try:
                preview_df = database.get_table_preview(table_name, limit=3)
                st.caption("Sample 3 Rows:")
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
            except Exception:
                pass

    # Database Re-seed Button
    if st.button("🔄 Reset / Re-seed Database", key="btn_reseed", use_container_width=True):
        database.init_database(force_recreate=True)
        st.success("Database re-seeded with fresh sample data!")
        st.rerun()

    # Query History
    if st.session_state.query_history:
        st.markdown("<hr style='margin: 1rem 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 0.82rem; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;'>Recent Queries</p>", unsafe_allow_html=True)
        for h_q in reversed(st.session_state.query_history[-4:]):
            if st.button(f"⏱️ {h_q[:35]}...", key=f"hist_{h_q}", use_container_width=True):
                set_query(h_q)


# =============================================================================
# 4. Main Executive Interface & KPI Summary Bar
# =============================================================================

# Hero Banner
st.markdown("""
<div class="exec-card" style="border-top: 4px solid #4F46E5; background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%); margin-bottom: 1rem;">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
        <div>
            <h1 style="font-size: 1.65rem; font-weight: 800; color: #0F172A; margin: 0 0 0.35rem 0; letter-spacing: -0.02em;">
                Natural Language SQL Data Analyst Agent
            </h1>
            <p style="font-size: 0.95rem; color: #475569; margin: 0; line-height: 1.5;">
                Autonomous LangGraph multi-stage state machine with self-correction, dynamic schema grounding, and interactive Plotly visualization.
            </p>
        </div>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <span class="pill-badge pill-indigo">LangGraph State Machine</span>
            <span class="pill-badge pill-emerald">SQLite Read-Only</span>
            <span class="pill-badge pill-amber">Self-Correction Guard</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Executive KPI Summary Bar
db_metrics = database.get_db_metrics()
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
            "Transaction volume by payment method"
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
    with st.spinner("LangGraph agent orchestrating query generation, execution, and synthesis..."):
        try:
            active_key = api_key_input.strip() if api_key_input else None
            state_result = agent.run_analyst_pipeline(
                user_query=user_query.strip(),
                api_key=active_key,
                model=selected_model,
                base_url=base_url_input
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

    expander_title = f"🧠 Agent Reasoning & State Trajectory ({len(thought_steps)} Steps"
    if has_self_correction:
        expander_title += f" &bull; ⚠️ {retry_count} Self-Correction Loop{'s' if retry_count > 1 else ''} Triggered)"
    else:
        expander_title += " &bull; ✅ Flawless Execution)"

    with st.expander(expander_title, expanded=True):
        st.markdown("""
        <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 0.85rem;">
            Inspect each state transition in the LangGraph workflow: query formulation, execution benchmark, runtime error capture, self-correction, and visual synthesis.
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
        # Narrative Insight Card
        st.markdown(f"""
        <div class="exec-card" style="border-left: 5px solid #2563EB;">
            <div class="exec-card-header">
                <span style="font-weight: 700; font-size: 1.05rem; color: #0F172A;">📊 Executive Business Insights</span>
                <span class="pill-badge pill-indigo">Automated Synthesis</span>
            </div>
            <div style="font-size: 0.95rem; color: #334155; line-height: 1.6;">
                {explanation}
            </div>
            {f'<div style="margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #E2E8F0; font-size: 0.85rem; color: #4338CA; font-weight: 600;">🎯 Key Actionable Takeaway: {chart_spec.get("takeaway", "")}</div>' if chart_spec and chart_spec.get("takeaway") else ''}
        </div>
        """, unsafe_allow_html=True)

        # Query-specific KPIs
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

        # Interactive Plotly Chart
        if not df.empty and chart_spec:
            c_type = chart_spec.get("chart_type", "bar")
            x_col = chart_spec.get("x")
            y_col = chart_spec.get("y")
            color_col = chart_spec.get("color")
            title = chart_spec.get("title", "Visual Analysis")

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
        st.markdown("""
        <div style="font-size: 0.88rem; color: #475569; margin-bottom: 0.5rem;">
            Verified SQLite syntax produced and validated by the LangGraph agent state machine:
        </div>
        """, unsafe_allow_html=True)
        st.code(sql_query, language="sql")

        exec_time = output.get("execution_time_ms", 0.0)
        retries = output.get("retry_count", 0)
        st.markdown(f"""
        <div style="display: flex; gap: 0.75rem; margin-top: 0.5rem;">
            <span class="pill-badge pill-indigo">⏱️ Execution Time: {exec_time} ms</span>
            <span class="pill-badge pill-emerald">🔄 Attempts: {retries + 1}</span>
            <span class="pill-badge pill-indigo">Database: analytics.db</span>
        </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # Tab 4: Direct SQL Sandbox (For Evaluators)
    # ---------------------------------------------------------
    with tab_sandbox:
        st.markdown("""
        <div style="font-size: 0.88rem; color: #475569; margin-bottom: 0.75rem;">
            Academic evaluators may test and cross-verify direct read-only SQL queries against <code>analytics.db</code>:
        </div>
        """, unsafe_allow_html=True)

        sandbox_sql = st.text_area(
            "Execute Raw SQL Query:",
            value=sql_query,
            height=120,
            key="sandbox_sql_input"
        )
        if st.button("⚡ Execute Custom Query", key="btn_run_sandbox"):
            try:
                s_df, s_dur = database.execute_query(sandbox_sql)
                st.success(f"Query returned {len(s_df)} row(s) in {s_dur} ms.")
                st.dataframe(s_df, use_container_width=True)
            except Exception as sb_err:
                st.error(f"Execution Error: {str(sb_err)}")

elif not output and not should_run:
    st.markdown("""
    <div class="exec-card" style="text-align: center; padding: 3rem 1.5rem; margin-top: 1rem;">
        <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">⚡</div>
        <h3 style="font-size: 1.25rem; font-weight: 700; color: #0F172A; margin: 0 0 0.5rem 0;">Ready to Analyze Your Data</h3>
        <p style="font-size: 0.9rem; color: #64748B; max-width: 600px; margin: 0 auto 1.5rem auto; line-height: 1.5;">
            Type any analytical inquiry in the box above or choose a curated executive prompt from the sidebar to observe the LangGraph agent generate queries, execute against SQLite, self-correct errors, and synthesize interactive visuals.
        </p>
        <div style="display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap;">
            <span class="pill-badge pill-indigo">Pydantic LLM Output</span>
            <span class="pill-badge pill-amber">Automated Retry Loop</span>
            <span class="pill-badge pill-emerald">Interactive Plotly Visuals</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
