"""The agent loop: parse -> detect -> investigate -> calculate -> recommend -> flag.

Each stage is a distinct, inspectable step. Stages 2+ are stubbed until the
later build steps; only stage 1 (read data) is real for now so the hello-world
can run end to end.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .trace import Trace

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"


def parse_data(trace: Trace) -> list[dict]:
    """Stage 1: read the transactions CSV into rows."""
    action = trace.start("parse_data", path=str(TRANSACTIONS_CSV))
    try:
        with TRANSACTIONS_CSV.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        action.finish({"row_count": len(rows), "columns": list(rows[0]) if rows else []})
        return rows
    except FileNotFoundError as exc:
        msg = f"transactions.csv not found at {TRANSACTIONS_CSV}"
        action.fail(msg)
        raise FileNotFoundError(msg) from exc


def run_pipeline() -> dict:
    """Run the full loop and return the result plus the step-by-step trace."""
    trace = Trace()

    try:
        rows = parse_data(trace)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "trace": trace.to_list()}

    # Stages 2+ are stubbed until later build steps.
    result = {
        "ok": True,
        "row_count": len(rows),
        "trace": trace.to_list(),
    }
    return result
