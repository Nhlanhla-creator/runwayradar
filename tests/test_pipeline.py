"""Pipeline smoke test — grows with each build step."""
from __future__ import annotations

from backend.pipeline import run_pipeline


def test_pipeline_runs_full_loop() -> None:
    """The full loop runs on the generated dataset and returns the trace."""
    result = run_pipeline()
    assert result["ok"] is True
    assert result["row_count"] > 0

    # Every stage in the loop recorded an action, in order.
    names = [step["name"] for step in result["trace"]]
    assert names == [
        "parse_data",
        "detect_anomalies",
        "investigate_candidate",
        "calculate_metrics",
        "generate_recommendations",
        "flag_for_action",
    ]
    assert all(step["status"] == "done" for step in result["trace"])

    # Hard numbers exist and are sane.
    assert result["metrics"]["runway_months"] > 0
    assert result["metrics"]["recent_monthly_burn"] > 0
    assert len(result["flagged"]) > 0
