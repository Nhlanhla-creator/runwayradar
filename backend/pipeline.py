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

# Header aliases for real bank exports and accounting CSVs
_HEADER_ALIASES = {
    "transaction date": "date",
    "date": "date",
    "posted date": "date",
    "posted": "date",
    "value date": "date",
    "vendor": "vendor",
    "description": "vendor",
    "merchant": "vendor",
    "payee": "vendor",
    "category": "category",
    "type": "category",
    "expense type": "category",
    "expense category": "category",
    "amount": "amount",
    "debit": "amount",
    "withdrawal": "amount",
    "value": "amount",
    "transaction amount": "amount",
    "recurring": "recurring",
    "is recurring": "recurring",
}

def _normalize_header(name: str) -> str:
    key = (name or "").strip().lower()
    return _HEADER_ALIASES.get(key, key)

def _parse_amount(raw: str) -> float:
    if raw is None:
        raise ValueError("empty amount")
    s = str(raw).strip()
    if not s:
        raise ValueError("empty amount")
    # Handle accounting negatives: (123.45) or -123.45
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "").replace(" ", "")
    val = float(s)
    return -val if negative else val

def _parse_date(raw: str) -> str:
    """Return normalized YYYY-MM-DD or raise ValueError."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty date")
    # Already good
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    # Try common US and EU formats
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"unrecognized date format: {raw!r}")


def _normalize_rows(raw_rows: list[dict]) -> list[dict]:
    """Map real-world headers to canonical keys and parse values tolerantly.

    Returns rows with keys: date (YYYY-MM-DD str), vendor, category, amount (float str for consistency with csv),
    recurring (str "true"/"false").
    """
    if not raw_rows:
        return []

    # Build a mapping from original header to canonical
    orig_headers = list(raw_rows[0].keys())
    header_map = {}
    for h in orig_headers:
        canon = _normalize_header(h)
        if canon in ("date", "vendor", "category", "amount", "recurring"):
            header_map[h] = canon

    normalized = []
    for r in raw_rows:
        row = {}
        for orig, canon in header_map.items():
            val = r.get(orig, "")
            row[canon] = val

        # Ensure required keys exist
        for key in ("date", "vendor", "category", "amount"):
            if key not in row:
                row[key] = ""

        # Parse date
        try:
            row["date"] = _parse_date(row["date"])
        except ValueError:
            row["date"] = str(row.get("date", "")).strip()

        # Parse amount to string that looks numeric (downstream does float())
        try:
            amt = _parse_amount(row["amount"])
            row["amount"] = f"{amt:.2f}"
        except Exception:
            row["amount"] = str(row.get("amount", "")).strip()

        # Recurring default
        rec = str(row.get("recurring", "")).strip().lower()
        row["recurring"] = "true" if rec in ("true", "yes", "1", "t") else "false"

        normalized.append(row)
    return normalized


def validate_rows(rows: list[dict]) -> None:
    """Raise ValueError with a clear message if rows do not match the schema.

    This now accepts common bank/accounting header variants and normalizes them.
    After calling this, rows are guaranteed to have the canonical keys.
    """
    if not rows:
        raise ValueError("The file has no data rows (only a header, or empty).")

    # Normalize in place so callers get canonical rows
    norm = _normalize_rows(rows)
    # Replace contents of the caller's list with normalized rows
    rows.clear()
    rows.extend(norm)

    if not rows:
        raise ValueError("The file has no data rows after normalization.")

    header = list(rows[0].keys())
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(
            "Missing required column(s) after normalization: " + ", ".join(missing) + ". "
            "We support common headers like: date/transaction date/posted, vendor/description/merchant, "
            "category/type, amount/debit, and optional recurring."
        )

    for i, row in enumerate(rows, start=2):
        date = str(row.get("date", "")).strip()
        if len(date) != 10 or date[4] != "-" or date[7] != "-":
            raise ValueError(f"Row {i}: date '{date}' could not be normalized to YYYY-MM-DD.")
        try:
            float(str(row.get("amount", "")).strip())
        except ValueError:
            raise ValueError(f"Row {i}: amount '{row.get('amount')}' is not a number after parsing.")
        if not str(row.get("vendor", "")).strip():
            raise ValueError(f"Row {i}: vendor/description is empty.")



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
