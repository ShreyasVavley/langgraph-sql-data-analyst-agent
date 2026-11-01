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


if __name__ == "__main__":
    pytest.main(["-v", "tests/test_pipeline.py"])
