"""The agent loop: parse -> detect -> investigate -> calculate -> recommend -> flag.

Each stage is a distinct, inspectable step. The pipeline accepts either the
bundled sample CSV or a caller-supplied list of rows (e.g. from an uploaded
file), so the whole loop runs over whatever dataset is current.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .stages.calculate import calculate_metrics
from .stages.detect import detect_anomalies
from .stages.flag import flag_for_action
from .stages.investigate import investigate_candidates
from .stages.recommend import generate_recommendations
from .trace import Trace

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"

REQUIRED_COLUMNS = ("date", "vendor", "category", "amount")
OPTIONAL_COLUMNS = ("recurring",)


def validate_rows(rows: list[dict]) -> None:
    """Raise ValueError with a clear message if rows do not match the schema.

    Rows keep their string values (exactly as csv.DictReader produces them);
    the downstream stages coerce amount/date themselves. We only guarantee the
    shape is sane here so a bad upload fails loudly instead of silently.

    `recurring` is optional: real bank exports rarely carry it, so a missing
    column defaults every row to non-recurring instead of rejecting the file.
    """
    if not rows:
        raise ValueError("The file has no data rows (only a header, or empty).")

    header = list(rows[0].keys())
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(
            "Missing required column(s): " + ", ".join(missing) + ". "
            "Expected columns: date, vendor, category, amount (recurring optional)."
        )

    if "recurring" not in header:
        for row in rows:
            row["recurring"] = "false"

    for i, row in enumerate(rows, start=2):  # 2 because row 1 is the header
        date = str(row.get("date", "")).strip()
        if len(date) != 10 or date[4] != "-" or date[7] != "-":
            raise ValueError(f"Row {i}: date '{date}' is not YYYY-MM-DD.")
        try:
            float(str(row.get("amount", "")).strip())
        except ValueError:
            raise ValueError(
                f"Row {i}: amount '{row.get('amount')}' is not a number."
            )
        if not str(row.get("vendor", "")).strip():
            raise ValueError(f"Row {i}: vendor is empty.")


def parse_data(trace: Trace, rows: list[dict] | None = None) -> list[dict]:
    """Stage 1: read transactions into rows (sample CSV or caller-supplied)."""
    action = trace.start("parse_data", path=str(TRANSACTIONS_CSV))
    if rows is None:
        try:
            with TRANSACTIONS_CSV.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError as exc:
            msg = f"transactions.csv not found at {TRANSACTIONS_CSV}"
            action.fail(msg)
            raise FileNotFoundError(msg) from exc

    validate_rows(rows)
    action.finish({"row_count": len(rows), "columns": list(rows[0])})
    return rows


def run_pipeline(rows: list[dict] | None = None) -> dict:
    """Run the full loop and return the result plus the step-by-step trace."""
    trace = Trace()

    try:
        rows = parse_data(trace, rows)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "trace": trace.to_list()}

    anomalies = detect_anomalies(trace, rows)
    investigated = investigate_candidates(trace, rows, anomalies)
    metrics = calculate_metrics(trace, rows, investigated)
    recommendations = generate_recommendations(trace, investigated)
    flagged = flag_for_action(trace, recommendations)

    return {
        "ok": True,
        "row_count": len(rows),
        "anomalies": investigated,
        "metrics": metrics,
        "recommendations": recommendations,
        "flagged": flagged,
        "trace": trace.to_list(),
    }
