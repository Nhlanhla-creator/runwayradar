"""Regression tests for the upload pipeline (no server required)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from backend import pipeline
from backend import qa

FIXTURE = Path(__file__).parent / "fixture_upload.csv"


def _rows() -> list[dict]:
    with FIXTURE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_sample_pipeline_runs():
    result = pipeline.run_pipeline(None)
    assert result["ok"] is True
    assert result["row_count"] == 181
    assert len(result["trace"]) == 6
    assert result["trace"][-1]["name"] == "flag_for_action"


def test_upload_pipeline_detects_duplicate():
    rows = _rows()
    result = pipeline.run_pipeline(rows)
    assert result["ok"] is True
    assert result["row_count"] == 4
    types = {a["type"] for a in result["anomalies"]}
    assert "duplicate_charge" in types
    assert result["anomalies"][0]["vendor"] == "Acme Corp"


def test_upload_works_without_recurring_column():
    rows = _rows()
    for r in rows:
        r.pop("recurring", None)
    result = pipeline.run_pipeline(rows)
    assert result["ok"] is True


def test_invalid_upload_rejected():
    with io.StringIO("date,vendor\n2025-01-05,Acme\n") as f:
        rows = list(csv.DictReader(f))
    import pytest

    with pytest.raises(ValueError):
        pipeline.validate_rows(rows)


def test_qa_answers_on_uploaded_rows():
    answer = qa.answer_question("What are my top issues?", _rows())
    assert answer["ok"] is True
    assert "flag_for_action" in answer["stages_consulted"]
