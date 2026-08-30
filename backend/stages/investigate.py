"""Stage 3: investigate each candidate anomaly by pulling related context.

For every candidate from the detect stage, this enriches it with the context an
analyst would look at before acting:

  - vendor history: that vendor's monthly spend across the whole period
  - category baseline: median monthly total for the candidate's category

It also runs one detector that needs *domain context* rather than a pure
statistical rule: lapsed-but-still-billing subscriptions. That is the seventh
planted anomaly type, and it is caught here because "this tool is redundant
with the one the team actually standardized on" is knowledge about tools, not a
number in a row.

The REDUNDANT_TOOL_PAIRS table is a small, explicit, documented knowledge base
— the equivalent of what an analyst already knows. It is intentionally tiny and
easy to audit.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median

from ..trace import Trace

# Old tool (still billing) -> newer tool the team standardized on. If both are
# still being paid, the old one is flagged as lapsed-but-still-billing.
REDUNDANT_TOOL_PAIRS = {
    "Canva Pro": "Figma",
}


def _vendor_monthly(rows: list[dict], vendor: str) -> list[dict]:
    monthly: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["vendor"] == vendor:
            monthly[r["date"][:7]] += float(r["amount"])
    return [
        {"month": m, "total": round(t, 2)}
        for m, t in sorted(monthly.items())
    ]


def _category_baseline(rows: list[dict], category: str) -> float:
    monthly: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["category"] == category:
            monthly[r["date"][:7]] += float(r["amount"])
    totals = list(monthly.values())
    return round(median(totals), 2) if totals else 0.0


def _detect_lapsed_subscriptions(rows: list[dict]) -> list[dict]:
    months = sorted({r["date"][:7] for r in rows})
    last_month = months[-1] if months else ""

    found = []
    for old_tool, new_tool in REDUNDANT_TOOL_PAIRS.items():
        old_active = any(r["vendor"] == old_tool and r["date"][:7] == last_month for r in rows)
        new_active = any(r["vendor"] == new_tool and r["date"][:7] == last_month for r in rows)
        if old_active and new_active:
            old_rows = [r for r in rows if r["vendor"] == old_tool]
            amount = float(old_rows[-1]["amount"]) if old_rows else 0.0
            found.append({
                "type": "lapsed_subscription_still_billing",
                "vendor": old_tool,
                "date": last_month,
                "amount": round(amount, 2),
                "reason": (
                    f"{old_tool} is still billing ({amount:.2f}) even though the "
                    f"team standardized on {new_tool}. Likely a lapsed subscription."
                ),
                "evidence": {"replacement": new_tool, "last_month": last_month},
            })
    return found


def investigate_candidates(trace: Trace, rows: list[dict], candidates: list[dict]) -> list[dict]:
    action = trace.start("investigate_candidate", candidate_count=len(candidates))

    enriched = []
    for c in candidates:
        vendor = c["vendor"]
        category = c.get("category")
        context = {
            "vendor_history": _vendor_monthly(rows, vendor),
            "category_baseline": _category_baseline(rows, category) if category else None,
        }
        enriched.append({**c, "context": context})

    # Domain-context detector: lapsed-but-still-billing subscriptions.
    lapsed = _detect_lapsed_subscriptions(rows)
    for c in lapsed:
        enriched.append({**c, "context": {
            "vendor_history": _vendor_monthly(rows, c["vendor"]),
            "category_baseline": None,
        }})

    action.finish({
        "investigated": len(candidates),
        "lapsed_subscriptions_found": len(lapsed),
        "total_after_investigation": len(enriched),
    })
    return enriched
