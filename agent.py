"""
agent.py
=============================================================================
LangGraph State Machine with Self-Correction Loop for Natural Language
to SQL Data Analytics.

Architecture:
  [User Query] 
       │
       ▼
  [generate_query] 
       │
       ▼
  [execute_query] ──────(Error & retry < 3)──────► [self_correct]
       │                                                 │
  (Success or max retries)                               │
       │                                                 │
       ▼                                                 │
  [synthesize_and_visualize] ◄───────────────────────────┘ (loops to execute_query)
       │
       ▼
     [END]
=============================================================================
"""

import os
import re
import json
import time
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Literal, Tuple
from pydantic import BaseModel, Field
import pandas as pd

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

import database


# =============================================================================
# 1. Pydantic Schemas for Structured LLM Outputs
# =============================================================================

class SQLQueryOutput(BaseModel):
    """Pydantic schema for initial SQL query generation."""
    sql_query: str = Field(
        ...,
        description="The clean, executable SQLite SELECT query answering the user's question. Do not include markdown ticks."
    )
    query_rationale: str = Field(
        ...,
        description="Concise rationale explaining table joins, filtering, and aggregation logic."
    )
    tables_used: List[str] = Field(
        default_factory=list,
        description="List of database tables referenced in the query."
    )
    confidence_score: float = Field(
        default=0.95,
        description="Confidence score between 0.0 and 1.0 indicating alignment with schema and query intent."
    )


class SQLCorrectionOutput(BaseModel):
    """Pydantic schema for query self-correction."""
    corrected_sql_query: str = Field(
        ...,
        description="The corrected, executable SQLite SELECT query resolving the syntax or schema error."
    )
    error_diagnosis: str = Field(
        ...,
        description="Clear diagnosis of what caused the execution error."
    )
    fix_applied: str = Field(
        ...,
        description="Summary of the changes made to fix the query."
    )


class KPIMetric(BaseModel):
    """Single KPI metric highlight."""
    label: str = Field(..., description="Short metric label (e.g., 'Total Revenue', 'Top Performer').")
    value: str = Field(..., description="Formatted value string (e.g., '$1,240,500', 'Enterprise Software').")
    delta: Optional[str] = Field(None, description="Optional trend or percentage context.")


class VisualizationInsightOutput(BaseModel):
    """Pydantic schema for final business insight and visualization specification."""
    explanation: str = Field(
        ...,
        description="An executive, high-level business summary of the results with numerical highlights and strategic analysis."
    )
    chart_type: Literal["bar", "line", "scatter", "pie", "area", "table"] = Field(
        ...,
        description="Optimal Plotly chart representation: 'bar' for categorical rankings, 'line' for chronological trends, 'area' for cumulative volume, 'scatter' for correlation, 'pie' for share of total (<6 items), or 'table' for text-heavy listings."
    )
    x_column: Optional[str] = Field(
        None,
        description="The DataFrame column to map to the X-axis (or categorical names for pie charts)."
    )
    y_column: Optional[str] = Field(
        None,
        description="The DataFrame column to map to the Y-axis (or values for pie charts)."
    )
    color_column: Optional[str] = Field(
        None,
        description="Optional column for categorical segmentation/grouping."
    )
    chart_title: str = Field(
        ...,
        description="A crisp, executive chart title."
    )
    key_takeaway: str = Field(
        ...,
        description="One punchy sentence summarizing the single most important actionable takeaway."
    )
    kpis: List[KPIMetric] = Field(
        default_factory=list,
        description="List of 2 to 4 prominent executive KPI cards derived from the data."
    )


# =============================================================================
# 2. LangGraph State Definition
# =============================================================================

class AgentState(TypedDict):
    """
    Core state object passed between nodes in the LangGraph state machine.
    Tracks user input, query evolution, error states, and visualization specifications.
    """
    user_query: str
    sql_query: str
    execution_error: Optional[str]
    dataframe_result: Optional[List[Dict[str, Any]]]
    dataframe_columns: Optional[List[str]]
    explanation: Optional[str]
    retry_count: int
    chart_spec: Optional[Dict[str, Any]]
    kpis: Optional[List[Dict[str, Any]]]
    thought_steps: List[Dict[str, Any]]
    execution_time_ms: float
    db_path: str


# =============================================================================
# 3. LLM Factory and Sanitization Helpers
# =============================================================================

def get_llm(api_key: Optional[str] = None, model: str = "gpt-4o-mini", base_url: Optional[str] = None):
    """Instantiates a ChatOpenAI model if an API key or custom endpoint is configured."""
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key and not base_url:
        return None
    try:
        kwargs = {
            "model": model,
            "temperature": 0.0,
            "api_key": key or "mock-key-for-local-endpoint"
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    except Exception:
        return None


def clean_sql_string(raw_sql: str) -> str:
    """Strips markdown code blocks, backticks, comments, and trailing semicolons/quotes."""
    cleaned = re.sub(r"^```(?:sql)?", "", raw_sql.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    cleaned = cleaned.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    return cleaned


# =============================================================================
# 4. Rich Analytical Rule Engine for Demonstration & Offline Robustness
# =============================================================================

ANALYTICAL_CATALOG = [
    {
        "keywords": ["top 5", "revenue", "product", "best selling"],
        "sql": """SELECT p.product_name, c.category_name, ROUND(SUM(oi.total_price), 2) AS total_revenue, SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status != 'Cancelled'
GROUP BY p.product_id, p.product_name, c.category_name
ORDER BY total_revenue DESC
LIMIT 5;""",
        "rationale": "Joined order_items with products, categories, and orders to calculate non-cancelled gross revenue per product.",
        "tables": ["order_items", "products", "categories", "orders"],
        "chart_type": "bar",
        "x": "product_name",
        "y": "total_revenue",
        "color": "category_name",
        "title": "Top 5 Revenue Generating Products"
    },
    {
        "keywords": ["segment", "sales", "monthly", "trend", "month"],
        "sql": """SELECT strftime('%Y-%m', o.order_date) AS month, c.segment, ROUND(SUM(oi.total_price), 2) AS monthly_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status != 'Cancelled'
GROUP BY month, c.segment
ORDER BY month ASC, monthly_revenue DESC;""",
        "rationale": "Grouped order revenue chronologically by month using strftime and segmented across customer tiers.",
        "tables": ["orders", "customers", "order_items"],
        "chart_type": "line",
        "x": "month",
        "y": "monthly_revenue",
        "color": "segment",
        "title": "Monthly Revenue Trends by Customer Segment"
    },
    {
        "keywords": ["region", "average order", "aov", "geographic"],
        "sql": """SELECT c.region, ROUND(AVG(order_totals.total_amount), 2) AS avg_order_value, COUNT(order_totals.order_id) AS order_count
FROM customers c
JOIN (
    SELECT o.order_id, o.customer_id, SUM(oi.total_price) AS total_amount
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status != 'Cancelled'
    GROUP BY o.order_id, o.customer_id
) AS order_totals ON c.customer_id = order_totals.customer_id
GROUP BY c.region
ORDER BY avg_order_value DESC;""",
        "rationale": "Subqueried total spend per individual order ID and averaged across customer geographic regions.",
        "tables": ["customers", "orders", "order_items"],
        "chart_type": "bar",
        "x": "region",
        "y": "avg_order_value",
        "title": "Average Order Value (AOV) by Geographic Region"
    },
    {
        "keywords": ["category", "profit", "margin", "profitable"],
        "sql": """SELECT c.category_name,
       ROUND(SUM(oi.total_price), 2) AS total_revenue,
       ROUND(SUM(oi.quantity * (oi.unit_price - p.cost_price)), 2) AS total_profit,
       ROUND((SUM(oi.quantity * (oi.unit_price - p.cost_price)) / SUM(oi.total_price)) * 100, 2) AS profit_margin_pct
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.category_name
ORDER BY total_profit DESC;""",
        "rationale": "Calculated total revenue, gross profit, and margin percentage across each business category.",
        "tables": ["order_items", "products", "categories", "orders"],
        "chart_type": "bar",
        "x": "category_name",
        "y": "profit_margin_pct",
        "title": "Profit Margin Percentage by Product Category"
    },
    {
        "keywords": ["order status", "status breakdown", "fulfillment", "distribution"],
        "sql": """SELECT status, COUNT(order_id) AS order_count, ROUND(SUM(shipping_cost), 2) AS total_shipping_fees
FROM orders
GROUP BY status
ORDER BY order_count DESC;""",
        "rationale": "Grouped total order count and aggregate logistics shipping fees by order fulfillment status.",
        "tables": ["orders"],
        "chart_type": "pie",
        "x": "status",
        "y": "order_count",
        "title": "Order Volume Distribution by Fulfillment Status"
    },
    {
        "keywords": ["customer", "top 10", "spend", "lifetime"],
        "sql": """SELECT c.name AS customer_name, c.segment, c.region, ROUND(SUM(oi.total_price), 2) AS total_spend, COUNT(DISTINCT o.order_id) AS orders_placed
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.customer_id, c.name, c.segment, c.region
ORDER BY total_spend DESC
LIMIT 10;""",
        "rationale": "Joined customers with orders and items to rank high-net-worth accounts by total spend.",
        "tables": ["customers", "orders", "order_items"],
        "chart_type": "bar",
        "x": "customer_name",
        "y": "total_spend",
        "color": "segment",
        "title": "Top 10 Enterprise & SMB Accounts by Lifetime Spend"
    },
    {
        "keywords": ["payment", "payment method", "wire", "credit card", "ach"],
        "sql": """SELECT payment_method, COUNT(order_id) AS total_transactions, ROUND(AVG(discount_percent * 100), 1) AS avg_discount_pct
FROM orders
GROUP BY payment_method
ORDER BY total_transactions DESC;""",
        "rationale": "Analyzed payment processor distributions and average customer discount incentives.",
        "tables": ["orders"],
        "chart_type": "pie",
        "x": "payment_method",
        "y": "total_transactions",
        "title": "Transaction Volume by Payment Method"
    }
]


def heuristic_generate_sql(user_query: str) -> Dict[str, Any]:
    """Generates a contextual SQL query if no active LLM API key is present."""
    q_lower = user_query.lower()

    # Intentional self-correction demo trigger
    if any(k in q_lower for k in ["error", "test correction", "test self-correction", "force error", "client_records"]):
        return {
            "sql": "SELECT client_name, SUM(order_val) FROM client_records GROUP BY 1;",
            "rationale": "Intentional syntactic/schema mismatch injected to demonstrate LangGraph's automated self-correction loop.",
            "tables": ["client_records (non-existent)"],
            "chart_type": "bar"
        }

    for item in ANALYTICAL_CATALOG:
        if any(kw in q_lower for kw in item["keywords"]):
            return {
                "sql": item["sql"],
                "rationale": item["rationale"],
                "tables": item.get("tables", []),
                "chart_type": item["chart_type"],
                "x": item.get("x"),
                "y": item.get("y"),
                "color": item.get("color"),
                "title": item.get("title")
            }

    # Dynamic fallback query
    return {
        "sql": """SELECT c.segment, c.region, COUNT(DISTINCT o.order_id) AS total_orders, ROUND(SUM(oi.total_price), 2) AS revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.segment, c.region
ORDER BY revenue DESC;""",
        "rationale": "Cross-sectional analysis aggregating revenue and order volume across customer segments and regions.",
        "tables": ["customers", "orders", "order_items"],
        "chart_type": "bar",
        "x": "segment",
        "y": "revenue",
        "color": "region",
        "title": "Revenue Breakdown by Segment and Region"
    }


def heuristic_self_correct(failed_sql: str, error_msg: str, user_query: str) -> Dict[str, Any]:
    """Deterministic correction for simulated error testing."""
    if "client_records" in failed_sql or "non_existent_column" in failed_sql:
        corrected = """SELECT c.name AS customer_name, c.segment, ROUND(SUM(oi.total_price), 2) AS total_spend
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.customer_id, c.name, c.segment
ORDER BY total_spend DESC
LIMIT 8;"""
        return {
            "sql": corrected,
            "diagnosis": "The previous query referenced a non-existent table 'client_records' and invalid column 'order_val'. Fixed by joining verified tables 'customers', 'orders', and 'order_items'.",
            "fix": "Replaced non-existent relation with valid customer spend aggregation."
        }

    return {
        "sql": """SELECT p.product_name, ROUND(SUM(oi.total_price), 2) AS revenue
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status != 'Cancelled'
GROUP BY p.product_name
ORDER BY revenue DESC LIMIT 5;""",
        "diagnosis": f"Encountered execution failure: {error_msg}. Rewrote query with standard verified product aggregation.",
        "fix": "Simplified joins and explicit table aliases."
    }


# =============================================================================
# 5. LangGraph Node Implementations
# =============================================================================

def create_agent_nodes(llm: Optional[ChatOpenAI] = None):
    """Factory returning the node execution functions for the LangGraph StateMachine."""

    def generate_query(state: AgentState) -> Dict[str, Any]:
        """Node 1: generate_query - Translates user query into verified SQLite query."""
        user_query = state["user_query"]
        db_path = state.get("db_path", database.DEFAULT_DB_PATH)
        schema_str = database.get_schema_string(db_path)
        thought_steps = list(state.get("thought_steps", []))
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Intentional test trigger check
        if any(k in user_query.lower() for k in ["test self-correction", "test correction", "force error"]):
            bad_sql = "SELECT client_name, SUM(order_val) FROM client_records GROUP BY 1;"
            thought_steps.append({
                "step": "Generating SQL Query",
                "status": "warning",
                "time": timestamp,
                "title": "1. SQL Generation (Self-Correction Demonstration)",
                "detail": "Deliberately injecting non-existent table 'client_records' to demonstrate LangGraph's automated error interception and recovery loop.",
                "sql": bad_sql,
                "tables_used": ["client_records (faulty)"]
            })
            return {
                "sql_query": bad_sql,
                "thought_steps": thought_steps,
                "retry_count": 0,
                "execution_error": None
            }

        if llm:
            try:
                system_prompt = f"""You are an elite SQL Data Analyst and Database Architect.
Generate an accurate, highly optimized SQLite query that directly answers the user's business question.

DATABASE SCHEMA:
{schema_str}

CRITICAL RULES:
1. ONLY produce SELECT queries. Do not generate DROP, DELETE, INSERT, or UPDATE statements.
2. Use valid SQLite functions (e.g., strftime('%Y-%m', date_col) for month extraction, ROUND(..., 2) for decimals).
3. Always qualify columns with table aliases when joining multiple tables.
4. Exclude cancelled orders (o.status != 'Cancelled') when analyzing revenue or order performance unless explicitly requested.
5. Provide clear, descriptive column aliases in the SELECT clause."""

                structured_llm = llm.with_structured_output(SQLQueryOutput)
                result: SQLQueryOutput = structured_llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_query)
                ])

                clean_sql = clean_sql_string(result.sql_query)
                thought_steps.append({
                    "step": "Generating SQL Query",
                    "status": "success",
                    "time": timestamp,
                    "title": "1. SQL Generation (LLM Reasoning)",
                    "detail": result.query_rationale,
                    "tables_used": result.tables_used,
                    "sql": clean_sql
                })
                return {
                    "sql_query": clean_sql,
                    "thought_steps": thought_steps,
                    "retry_count": 0,
                    "execution_error": None
                }
            except Exception:
                pass

        # Heuristic / Offline fallback
        h_res = heuristic_generate_sql(user_query)
        thought_steps.append({
            "step": "Generating SQL Query",
            "status": "success",
            "time": timestamp,
            "title": "1. SQL Generation (Analytical Parser)",
            "detail": h_res["rationale"],
            "tables_used": h_res.get("tables", []),
            "sql": h_res["sql"]
        })
        return {
            "sql_query": h_res["sql"],
            "thought_steps": thought_steps,
            "retry_count": 0,
            "execution_error": None
        }

    def execute_query(state: AgentState) -> Dict[str, Any]:
        """Node 2: execute_query - Runs SQL against SQLite with performance timing & traceback capture."""
        sql_query = state["sql_query"]
        db_path = state.get("db_path", database.DEFAULT_DB_PATH)
        thought_steps = list(state.get("thought_steps", []))
        timestamp = datetime.now().strftime("%H:%M:%S")

        try:
            df, duration_ms = database.execute_query(sql_query, db_path)
            thought_steps.append({
                "step": "Executing Query",
                "status": "success",
                "time": timestamp,
                "title": f"2. Query Execution Success (Attempt {state.get('retry_count', 0) + 1})",
                "detail": f"Database executed query successfully in {duration_ms} ms. Retrieved {len(df)} rows across {len(df.columns)} columns.",
                "rows_retrieved": len(df),
                "columns": list(df.columns),
                "duration_ms": duration_ms
            })
            return {
                "execution_error": None,
                "dataframe_result": df.to_dict(orient="records"),
                "dataframe_columns": list(df.columns),
                "execution_time_ms": duration_ms,
                "thought_steps": thought_steps
            }
        except Exception as err:
            err_tb = traceback.format_exc()
            short_err = str(err)
            thought_steps.append({
                "step": "Executing Query",
                "status": "error",
                "time": timestamp,
                "title": f"2. Query Execution Failure (Attempt {state.get('retry_count', 0) + 1})",
                "detail": f"SQLite execution failed: {short_err}",
                "error_traceback": err_tb,
                "failed_sql": sql_query
            })
            return {
                "execution_error": short_err,
                "dataframe_result": None,
                "dataframe_columns": None,
                "thought_steps": thought_steps
            }

    def self_correct(state: AgentState) -> Dict[str, Any]:
        """Node 3: self_correct - Intercepts error traceback and rewrites the SQL query."""
        user_query = state["user_query"]
        failed_sql = state["sql_query"]
        error_msg = state.get("execution_error", "Unknown Execution Error")
        retry_count = state.get("retry_count", 0) + 1
        db_path = state.get("db_path", database.DEFAULT_DB_PATH)
        schema_str = database.get_schema_string(db_path)
        thought_steps = list(state.get("thought_steps", []))
        timestamp = datetime.now().strftime("%H:%M:%S")

        if llm:
            try:
                system_prompt = f"""You are an expert SQLite Query Debugger and Self-Correction Agent.
A previously generated query failed with a runtime error. Inspect the schema and traceback to write a corrected query.

DATABASE SCHEMA:
{schema_str}

FAILED SQL:
{failed_sql}

ERROR MESSAGE:
{error_msg}

USER GOAL:
{user_query}

INSTRUCTIONS:
1. Identify the exact root cause (missing table/column, invalid GROUP BY, aggregate syntax).
2. Rewrite the query strictly adhering to verified schema tables.
3. Keep the query read-only (SELECT only)."""

                structured_llm = llm.with_structured_output(SQLCorrectionOutput)
                correction: SQLCorrectionOutput = structured_llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Fix the query that failed with: {error_msg}")
                ])

                clean_corrected_sql = clean_sql_string(correction.corrected_sql_query)
                thought_steps.append({
                    "step": "Self-Correction Loop",
                    "status": "corrected",
                    "time": timestamp,
                    "title": f"3. Self-Correction Triggered (Retry {retry_count}/3)",
                    "detail": f"Diagnosis: {correction.error_diagnosis}\nFix Applied: {correction.fix_applied}",
                    "sql": clean_corrected_sql
                })
                return {
                    "sql_query": clean_corrected_sql,
                    "retry_count": retry_count,
                    "thought_steps": thought_steps,
                    "execution_error": None
                }
            except Exception:
                pass

        # Heuristic correction fallback
        h_corr = heuristic_self_correct(failed_sql, error_msg, user_query)
        thought_steps.append({
            "step": "Self-Correction Loop",
            "status": "corrected",
            "time": timestamp,
            "title": f"3. Self-Correction Triggered (Retry {retry_count}/3)",
            "detail": f"Diagnosis: {h_corr['diagnosis']}\nFix Applied: {h_corr['fix']}",
            "sql": h_corr["sql"]
        })
        return {
            "sql_query": h_corr["sql"],
            "retry_count": retry_count,
            "thought_steps": thought_steps,
            "execution_error": None
        }

    def synthesize_and_visualize(state: AgentState) -> Dict[str, Any]:
        """Node 4: synthesize_and_visualize - Generates executive insight and Plotly configuration."""
        user_query = state["user_query"]
        records = state.get("dataframe_result")
        columns = state.get("dataframe_columns") or []
        thought_steps = list(state.get("thought_steps", []))
        timestamp = datetime.now().strftime("%H:%M:%S")

        if not records or len(records) == 0:
            error_reason = state.get("execution_error")
            if error_reason:
                msg = f"Unable to retrieve records after self-correction attempts. Root cause: {error_reason}"
            else:
                msg = "The query executed successfully but yielded 0 matching records for the selected filters."

            thought_steps.append({
                "step": "Synthesizing Insights",
                "status": "warning",
                "time": timestamp,
                "title": "4. Insight Synthesis (No Records Returned)",
                "detail": msg
            })
            return {
                "explanation": msg,
                "chart_spec": None,
                "kpis": [],
                "thought_steps": thought_steps
            }

        df = pd.DataFrame(records)

        if llm:
            try:
                data_sample = df.head(10).to_dict(orient="records")
                data_summary = f"Columns: {columns}\nRow Count: {len(df)}\nSample Rows:\n{json.dumps(data_sample, indent=2, default=str)}"

                system_prompt = f"""You are a Principal Business Intelligence Analyst and Data Storyteller.
Analyze the user's inquiry and the query results.
Generate:
1. An executive insight narrative summarizing the findings, key trends, and notable metrics.
2. The optimal visualization type:
   - 'bar': when comparing categories, rankings, or discrete groups.
   - 'line': when the X-axis is chronological (date, month, year).
   - 'area': when showing cumulative or volume trends over time.
   - 'scatter': when analyzing correlations between two continuous numeric variables.
   - 'pie': when showing proportional parts of a whole (best if <= 6 distinct categories).
   - 'table': if the output is text-heavy or high-cardinality listings.
3. The exact column names to map to x, y, and optional color grouping.
4. A punchy one-sentence key takeaway.
5. 2 to 4 prominent executive KPI metrics (label and formatted value)."""

                structured_llm = llm.with_structured_output(VisualizationInsightOutput)
                vis_output: VisualizationInsightOutput = structured_llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"User Query: {user_query}\n\nDataset Summary:\n{data_summary}")
                ])

                chart_spec = {
                    "chart_type": vis_output.chart_type,
                    "x": vis_output.x_column if vis_output.x_column in df.columns else (df.columns[0] if len(df.columns) > 0 else None),
                    "y": vis_output.y_column if vis_output.y_column in df.columns else (df.columns[1] if len(df.columns) > 1 else None),
                    "color": vis_output.color_column if vis_output.color_column in df.columns else None,
                    "title": vis_output.chart_title,
                    "takeaway": vis_output.key_takeaway
                }

                kpis_data = [k.model_dump() for k in vis_output.kpis] if vis_output.kpis else infer_kpis_heuristic(df)

                thought_steps.append({
                    "step": "Synthesizing Insights",
                    "status": "success",
                    "time": timestamp,
                    "title": "4. Visualization & Business Synthesis",
                    "detail": f"Optimal visual: {vis_output.chart_type.upper()} mapping '{chart_spec['x']}' -> '{chart_spec['y']}'.\nTakeaway: {vis_output.key_takeaway}",
                    "chart_spec": chart_spec
                })

                return {
                    "explanation": vis_output.explanation,
                    "chart_spec": chart_spec,
                    "kpis": kpis_data,
                    "thought_steps": thought_steps
                }
            except Exception:
                pass

        # Heuristic synthesis and KPI generation
        chart_spec, explanation, kpis_data = infer_visualization_heuristic(df, user_query)
        thought_steps.append({
            "step": "Synthesizing Insights",
            "status": "success",
            "time": timestamp,
            "title": "4. Visualization & Heuristic Synthesis",
            "detail": f"Inferred optimal visualization: {chart_spec['chart_type'].upper()} chart based on dataset dimensions.",
            "chart_spec": chart_spec
        })

        return {
            "explanation": explanation,
            "chart_spec": chart_spec,
            "kpis": kpis_data,
            "thought_steps": thought_steps
        }

    return generate_query, execute_query, self_correct, synthesize_and_visualize


def infer_kpis_heuristic(df: pd.DataFrame) -> List[Dict[str, str]]:
    """Derives prominent executive KPI cards from DataFrame columns."""
    kpis = []
    cols = list(df.columns)
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]

    if numeric_cols:
        primary_num = numeric_cols[0]
        total_val = df[primary_num].sum()
        avg_val = df[primary_num].mean()

        is_currency = any(w in primary_num.lower() for w in ["rev", "price", "spend", "cost", "profit", "amount", "total"])
        fmt_total = f"${total_val:,.2f}" if is_currency else f"{total_val:,.1f}"
        fmt_avg = f"${avg_val:,.2f}" if is_currency else f"{avg_val:,.1f}"

        kpis.append({"label": f"Aggregate {primary_num.replace('_', ' ').title()}", "value": fmt_total})
        kpis.append({"label": f"Average {primary_num.replace('_', ' ').title()}", "value": fmt_avg})

        cat_cols = [c for c in cols if c not in numeric_cols]
        if cat_cols and len(df) > 0:
            max_idx = df[primary_num].idxmax()
            top_entity = str(df.loc[max_idx, cat_cols[0]])
            kpis.append({"label": "Top Performer", "value": top_entity})

    kpis.append({"label": "Records Analyzed", "value": f"{len(df):,}"})
    return kpis[:4]


def infer_visualization_heuristic(df: pd.DataFrame, user_query: str) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
    """Infers chart mapping, summary, and KPIs when LLM synthesis is offline."""
    cols = list(df.columns)
    if len(cols) == 1:
        chart_spec = {
            "chart_type": "table",
            "x": cols[0],
            "y": None,
            "color": None,
            "title": "Query Results Preview",
            "takeaway": f"Retrieved {len(df)} records."
        }
        explanation = f"Query executed successfully, returning {len(df)} record(s) for metric `{cols[0]}`: {df[cols[0]].iloc[0] if len(df) > 0 else 'N/A'}."
        kpis = [{"label": cols[0].title(), "value": str(df[cols[0]].iloc[0]) if len(df) > 0 else "0"}]
        return chart_spec, explanation, kpis

    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    date_cols = [c for c in cols if any(w in c.lower() for w in ["date", "month", "year", "time", "day"])]
    cat_cols = [c for c in cols if c not in numeric_cols and c not in date_cols]

    chart_type = "bar"
    x_col = cols[0]
    y_col = numeric_cols[0] if numeric_cols else cols[1]
    color_col = cat_cols[1] if len(cat_cols) > 1 else None

    # Trend detection
    if date_cols and numeric_cols:
        chart_type = "line"
        x_col = date_cols[0]
        y_col = numeric_cols[0]
    elif len(df) <= 6 and numeric_cols and any(w in user_query.lower() for w in ["share", "proportion", "breakdown", "distribution"]):
        chart_type = "pie"
        x_col = cat_cols[0] if cat_cols else cols[0]
        y_col = numeric_cols[0]
    elif len(numeric_cols) >= 2 and any(w in user_query.lower() for w in ["scatter", "correlation", "vs", "versus"]):
        chart_type = "scatter"
        x_col = numeric_cols[0]
        y_col = numeric_cols[1]

    title = f"{y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}"

    if numeric_cols and len(df) > 0:
        max_idx = df[y_col].idxmax()
        top_name = df.loc[max_idx, x_col]
        top_val = df.loc[max_idx, y_col]
        sum_val = df[y_col].sum()

        is_curr = any(w in y_col.lower() for w in ["rev", "spend", "price", "profit", "amount"])
        val_display = f"${top_val:,.2f}" if is_curr else f"{top_val:,.1f}"
        sum_display = f"${sum_val:,.2f}" if is_curr else f"{sum_val:,.1f}"

        explanation = (
            f"**Executive Briefing:** Analysis indicates that **{top_name}** leads the cohort with **{val_display}**, "
            f"commanding an outsized portion of the aggregate total (**{sum_display}** across {len(df)} records). "
            f"The underlying distribution exhibits healthy operational volume with strategic concentration in top accounts."
        )
        takeaway = f"{top_name} is the primary growth driver for {y_col.replace('_', ' ')}."
    else:
        explanation = f"Retrieved {len(df)} records matching the query parameters."
        takeaway = "Data extracted cleanly across active relational tables."

    chart_spec = {
        "chart_type": chart_type,
        "x": x_col,
        "y": y_col,
        "color": color_col,
        "title": title,
        "takeaway": takeaway
    }

    kpis = infer_kpis_heuristic(df)
    return chart_spec, explanation, kpis


# =============================================================================
# 6. Routing and Graph Compilation
# =============================================================================

def should_continue(state: AgentState) -> str:
    """
    Conditional routing edge after `execute_query`:
    - If execution succeeded: route to `synthesize_and_visualize`.
    - If execution failed and retry_count < 3: route to `self_correct`.
    - If retry_count >= 3: route to `synthesize_and_visualize` with error notes.
    """
    execution_error = state.get("execution_error")
    retry_count = state.get("retry_count", 0)

    if execution_error is not None:
        if retry_count < 3:
            return "self_correct"
        else:
            return "synthesize_and_visualize"

    return "synthesize_and_visualize"


def build_analyst_graph(llm: Optional[ChatOpenAI] = None):
    """Constructs and compiles the complete LangGraph StateMachine."""
    generate_node, execute_node, correct_node, synthesize_node = create_agent_nodes(llm)

    workflow = StateGraph(AgentState)

    workflow.add_node("generate_query", generate_node)
    workflow.add_node("execute_query", execute_node)
    workflow.add_node("self_correct", correct_node)
    workflow.add_node("synthesize_and_visualize", synthesize_node)

    workflow.set_entry_point("generate_query")
    workflow.add_edge("generate_query", "execute_query")

    workflow.add_conditional_edges(
        "execute_query",
        should_continue,
        {
            "self_correct": "self_correct",
            "synthesize_and_visualize": "synthesize_and_visualize"
        }
    )

    workflow.add_edge("self_correct", "execute_query")
    workflow.add_edge("synthesize_and_visualize", END)

    return workflow.compile()


def run_analyst_pipeline(
    user_query: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    base_url: Optional[str] = None,
    db_path: str = database.DEFAULT_DB_PATH
) -> AgentState:
    """Convenience orchestrator executing the end-to-end LangGraph pipeline."""
    llm = get_llm(api_key=api_key, model=model, base_url=base_url)
    app = build_analyst_graph(llm=llm)

    initial_state: AgentState = {
        "user_query": user_query,
        "sql_query": "",
        "execution_error": None,
        "dataframe_result": None,
        "dataframe_columns": None,
        "explanation": None,
        "retry_count": 0,
        "chart_spec": None,
        "kpis": [],
        "thought_steps": [],
        "execution_time_ms": 0.0,
        "db_path": db_path
    }

    final_state = app.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    print("Testing LangGraph Analyst Pipeline...")
    res = run_analyst_pipeline("What are the top 5 revenue generating products?")
    print(f"Generated SQL:\n{res['sql_query']}")
    print(f"\nKPIs: {res['kpis']}")
    print(f"\nTakeaway: {res['chart_spec']['takeaway']}")
