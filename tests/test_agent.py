"""
tests/test_agent.py
=============================================================================
Automated test suite for agent.py (Pydantic schemas, Nodes, and Graph wiring).
=============================================================================
"""

import pytest
import pandas as pd
from pydantic import ValidationError

import agent
import database


def test_pydantic_schemas():
    """Verify validation and serialization of Pydantic models."""
    # SQLQueryOutput
    q_out = agent.SQLQueryOutput(
        sql_query="SELECT * FROM customers;",
        query_rationale="Fetches customer records",
        tables_used=["customers"],
        confidence_score=0.98
    )
    assert q_out.sql_query == "SELECT * FROM customers;"
    assert q_out.confidence_score == 0.98

    # SQLCorrectionOutput
    c_out = agent.SQLCorrectionOutput(
        corrected_sql_query="SELECT name FROM customers;",
        error_diagnosis="Column did not exist",
        fix_applied="Mapped to valid column name"
    )
    assert "customers" in c_out.corrected_sql_query

    # VisualizationInsightOutput
    v_out = agent.VisualizationInsightOutput(
        explanation="Revenue is concentrated in Enterprise accounts.",
        chart_type="bar",
        x_column="name",
        y_column="spend",
        chart_title="Account Spend",
        key_takeaway="Enterprise accounts yield highest return.",
        kpis=[{"label": "Top Account", "value": "Apex Global"}]
    )
    assert v_out.chart_type == "bar"
    assert len(v_out.kpis) == 1


def test_clean_sql_string():
    """Verify code block stripper."""
    raw = "```sql\nSELECT * FROM orders;\n```"
    assert agent.clean_sql_string(raw) == "SELECT * FROM orders;"

    quoted = "'SELECT 1;'"
    assert agent.clean_sql_string(quoted) == "SELECT 1;"


def test_heuristic_sql_generation():
    """Verify heuristic mapping on analytical catalog queries."""
    res = agent.heuristic_generate_sql("What are the top 5 revenue generating products?")
    assert "order_items" in res["sql"].lower()
    assert "limit 5" in res["sql"].lower()
    assert res["chart_type"] == "bar"

    res_trend = agent.heuristic_generate_sql("monthly sales trend by segment")
    assert "strftime" in res_trend["sql"].lower()
    assert res_trend["chart_type"] == "line"


def test_node_functions():
    """Verify individual node function contracts."""
    generate_node, execute_node, correct_node, synthesize_node = agent.create_agent_nodes(llm=None)

    # 1. Test generate_query
    state_in: agent.AgentState = {
        "user_query": "What are the top 5 revenue generating products?",
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
        "db_path": database.DEFAULT_DB_PATH
    }
    gen_out = generate_node(state_in)
    assert len(gen_out["sql_query"]) > 0
    assert len(gen_out["thought_steps"]) == 1

    # 2. Test execute_query
    state_exec = {**state_in, **gen_out}
    exec_out = execute_node(state_exec)
    assert exec_out["execution_error"] is None
    assert exec_out["dataframe_result"] is not None
    assert len(exec_out["dataframe_result"]) > 0

    # 3. Test synthesize_and_visualize
    state_synth = {**state_exec, **exec_out}
    synth_out = synthesize_node(state_synth)
    assert synth_out["explanation"] is not None
    assert synth_out["chart_spec"] is not None
    assert len(synth_out["kpis"]) > 0


def test_graph_compilation():
    """Verify the compiled LangGraph workflow object."""
    graph = agent.build_analyst_graph(llm=None)
    assert graph is not None


if __name__ == "__main__":
    pytest.main(["-v", "tests/test_agent.py"])
