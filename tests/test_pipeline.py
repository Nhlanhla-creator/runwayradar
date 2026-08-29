"""Smoke test for the pipeline — grows with each build step."""
from __future__ import annotations

from backend.pipeline import run_pipeline


def test_pipeline_reports_missing_csv() -> None:
    """Before the dataset exists, the pipeline should fail cleanly with a trace."""
    result = run_pipeline()
    assert result["ok"] is False
    assert "not found" in result["error"].lower()
    assert result["trace"], "a failing run must still produce a trace"
    assert result["trace"][0]["name"] == "parse_data"
    assert result["trace"][0]["status"] == "failed"
