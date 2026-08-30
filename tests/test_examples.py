"""Regression tests for multiple example CSVs with real-world formats."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from backend import pipeline

EXAMPLES_DIR = Path(__file__).parent.parent / "data" / "examples"


def _load_raw(name: str) -> list[dict]:
    p = EXAMPLES_DIR / name
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("name", [
    "bank-export.csv",
    "accounting.csv",
    "startup-creep.csv",
    "eu-dates.csv",
])
def test_example_is_recognized_and_produces_results(name: str):
    raw = _load_raw(name)
    rows = list(raw)
    # Should not raise
    pipeline.validate_rows(rows)
    result = pipeline.run_pipeline(rows)
    assert result["ok"] is True
    assert result["row_count"] > 0
    # At least some anomalies or metrics should be present
    assert "anomalies" in result
    assert "metrics" in result


def test_sample_still_works():
    result = pipeline.run_pipeline(None)
    assert result["ok"] is True
    assert result["row_count"] >= 100
