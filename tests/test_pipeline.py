"""
tests/test_pipeline.py
=============================================================================
End-to-End Pipeline & Self-Correction Verification Suite.
=============================================================================
"""

import pytest
import agent
import database


def test_standard_pipeline_execution():
    """Verify clean execution without errors for standard user queries."""
    queries = [
        "What are the top 5 revenue generating products?",
        "Show monthly sales trends by customer segment",
        "Which region has the highest average order value?"
    ]

    for q in queries:
        result = agent.run_analyst_pipeline(user_query=q)
        assert result["execution_error"] is None
        assert result["retry_count"] == 0
        assert result["dataframe_result"] is not None
        assert len(result["dataframe_result"]) > 0
        assert result["chart_spec"] is not None
        assert result["chart_spec"]["x"] in result["dataframe_columns"]
        assert len(result["thought_steps"]) >= 3


def test_self_correction_loop():
    """
    Verify that an intentional SQL error triggers the self-correction node,
    increments retry_count, and successfully recovers.
    """
    # Trigger intentional error
    result = agent.run_analyst_pipeline("Test self-correction: Select client_name and total sales from client_records")

    # 1. State must reflect that self-correction occurred
    assert result["retry_count"] == 1, f"Expected retry_count == 1, got {result['retry_count']}"
    assert result["execution_error"] is None, "State must clear execution error after successful recovery"

    # 2. Results must be populated
    assert result["dataframe_result"] is not None
    assert len(result["dataframe_result"]) > 0

    # 3. Thought steps must record the error, diagnosis, and fix
    step_titles = [s["title"] for s in result["thought_steps"]]
    assert any("Self-Correction Demonstration" in t for t in step_titles)
    assert any("Query Execution Failure" in t or "Query Execution Error" in t for t in step_titles)
    assert any("Self-Correction Triggered" in t for t in step_titles)
    assert any("Query Execution Success" in t for t in step_titles)


def test_routing_logic():
    """Verify should_continue edge conditions."""
    # Success condition
    state_ok: agent.AgentState = {"execution_error": None, "retry_count": 0}  # type: ignore
    assert agent.should_continue(state_ok) == "synthesize_and_visualize"

    # Retry condition (attempts < 3)
    state_err_1: agent.AgentState = {"execution_error": "Syntax error", "retry_count": 0}  # type: ignore
    assert agent.should_continue(state_err_1) == "self_correct"

    state_err_2: agent.AgentState = {"execution_error": "Syntax error", "retry_count": 2}  # type: ignore
    assert agent.should_continue(state_err_2) == "self_correct"

    # Exhausted retries condition (>= 3)
    state_exhausted: agent.AgentState = {"execution_error": "Fatal syntax error", "retry_count": 3}  # type: ignore
    assert agent.should_continue(state_exhausted) == "synthesize_and_visualize"


def test_custom_engine_pipeline_execution(tmp_path):
    """Verify that run_analyst_pipeline runs end-to-end with a custom dynamic SQLAlchemy engine."""
    from sqlalchemy import create_engine, text

    custom_db_file = tmp_path / "custom_company.db"
    custom_uri = f"sqlite:///{custom_db_file}"
    custom_engine = database.create_custom_engine(custom_uri)

    with custom_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE employees (
                emp_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                salary REAL NOT NULL
            );
        """))
        conn.execute(text("""
            INSERT INTO employees (emp_id, name, department, salary) VALUES
            (1, 'Alice Chen', 'Engineering', 125000.0),
            (2, 'Bob Smith', 'Sales', 95000.0),
            (3, 'Carlos Rivera', 'Engineering', 135000.0),
            (4, 'Diana Patel', 'Marketing', 110000.0);
        """))
        conn.commit()

    # Run the pipeline with the custom engine
    result = agent.run_analyst_pipeline(
        user_query="Show employees in Engineering",
        engine=custom_engine
    )

    assert result["execution_error"] is None
    assert result["retry_count"] == 0
    assert result["dataframe_result"] is not None
    assert len(result["dataframe_result"]) > 0
    assert result["db_dialect"] == "sqlite"
    assert "employees" in result["sql_query"].lower()
    assert result["chart_spec"] is not None

    # Teardown
    custom_engine.dispose()


if __name__ == "__main__":
    pytest.main(["-v", "tests/test_pipeline.py"])
