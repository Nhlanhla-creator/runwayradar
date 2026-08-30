"""Ask-a-question: a keyless, deterministic intent matcher.

Maps a natural-language question to the pipeline stage(s) that answer it, runs
just those stages, and returns a plain-English answer plus the stages consulted.
No LLM, no API key, no network — it runs reliably offline.

This is deliberately separate from the full /api/run loop: asking "what's my
burn rate?" should re-run only calculate_metrics, not re-flag everything.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .stages.calculate import calculate_metrics
from .stages.detect import detect_anomalies
from .stages.flag import flag_for_action
from .stages.investigate import investigate_candidates
from .stages.recommend import generate_recommendations
from .trace import Trace

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"


def _load_rows(rows: list[dict] | None) -> list[dict]:
    if rows is not None:
        return rows
    with TRANSACTIONS_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _run_full(rows: list[dict] | None) -> dict:
    """Run the whole loop once, so every answer has fresh context."""
    trace = Trace()
    rows = _load_rows(rows)
    anomalies = detect_anomalies(trace, rows)
    investigated = investigate_candidates(trace, rows, anomalies)
    metrics = calculate_metrics(trace, rows, investigated)
    recommendations = generate_recommendations(trace, investigated)
    flagged = flag_for_action(trace, recommendations)
    return {
        "rows": rows,
        "anomalies": investigated,
        "metrics": metrics,
        "recommendations": recommendations,
        "flagged": flagged,
        "trace": trace.to_list(),
    }


def _fmt_money(n: float) -> str:
    return f"${n:,.0f}"


def _top_vendors(rows: list[dict], n: int = 5) -> list[tuple[str, float]]:
    totals = defaultdict(float)
    for r in rows:
        totals[r["vendor"]] += float(r["amount"])
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:n]


def _vendor_for_question(q: str, data: dict) -> dict | None:
    """Return the anomaly whose vendor is named in the question, if any."""
    for a in data["anomalies"]:
        vendor = a["vendor"].lower()
        if vendor and len(vendor) > 2 and vendor in q:
            return a
    return None


def answer_question(question: str, rows: list[dict] | None = None) -> dict:
    """Return {answer, stages_consulted, ok} for a natural-language question."""
    q = (question or "").strip().lower()
    if not q:
        return {
            "ok": False,
            "answer": "Ask me something, e.g. 'What is my burn rate?'",
            "stages_consulted": [],
        }

    data = _run_full(rows)
    m = data["metrics"]

    # --- a specific vendor, asked before the generic "issues" branch so
    #     "why is Notion flagged?" returns Notion's reason, not the top-5 ---
    vendor_anomaly = _vendor_for_question(q, data)
    if vendor_anomaly is not None:
        history = (vendor_anomaly.get("context") or {}).get("vendor_history") or []
        hist_tail = ""
        if history:
            hist_tail = " Monthly history: " + ", ".join(
                f"{h['month']}={_fmt_money(h['total'])}" for h in history
            ) + "."
        return {
            "ok": True,
            "answer": f"{vendor_anomaly['reason']}{hist_tail}",
            "stages_consulted": ["detect_anomalies", "investigate_candidate"],
        }

    # --- top / biggest vendors ---
    if any(w in q for w in ("vendor", "vendors", "merchant", "who do i pay", "pay the most")):
        if any(w in q for w in ("top", "biggest", "largest", "most", "highest")):
            vendors = _top_vendors(data["rows"])
            lines = [f"{_fmt_money(v)} — {name}" for name, v in vendors]
            return {
                "ok": True,
                "answer": "Your biggest vendors by total spend:\n• " + "\n• ".join(lines),
                "stages_consulted": ["parse_data", "calculate_metrics"],
            }
        # generic "vendor" mention falls through to help

    # --- burn rate ---
    if any(w in q for w in ("burn", "spend", "spending", "monthly")):
        return {
            "ok": True,
            "answer": (
                f"Your recent monthly burn is {_fmt_money(m['recent_monthly_burn'])} "
                f"(across the last 3 months), versus an all-time average of "
                f"{_fmt_money(m['avg_monthly_burn'])} over {m['months_covered']} months."
            ),
            "stages_consulted": ["calculate_metrics"],
        }

    # --- runway ---
    if any(w in q for w in ("runway", "how long", "cash", "out of money", "out of cash")):
        return {
            "ok": True,
            "answer": (
                f"At {_fmt_money(m['recent_monthly_burn'])}/mo burn against "
                f"{_fmt_money(m['starting_cash'])} cash, you have about "
                f"{m['runway_months']:.1f} months of runway."
            ),
            "stages_consulted": ["calculate_metrics"],
        }

    # --- anomalies / issues / flags ---
    if any(w in q for w in ("anomal", "issue", "flag", "problem", "wrong", "top", "cost")):
        flagged = data["flagged"]
        lines = [
            f"{_fmt_money(f['annual_cost_estimate'])}/yr — {f['vendor']}: {f['recommendation']}"
            for f in flagged
        ]
        return {
            "ok": True,
            "answer": "Top issues flagged for action:\n• " + "\n• ".join(lines),
            "stages_consulted": ["flag_for_action", "generate_recommendations"],
        }

    # --- help ---
    return {
        "ok": True,
        "answer": (
            "I can answer: 'What is my burn rate?', 'How much runway do I have?', "
            "'What are my top issues?', 'Who are my biggest vendors?', or ask about "
            "a specific vendor like 'Why is Notion flagged?'."
        ),
        "stages_consulted": [],
    }
