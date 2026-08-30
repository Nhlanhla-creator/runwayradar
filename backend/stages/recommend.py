"""Stage 5: turn anomalies into prioritized recommendations.

Recommendations are keyed to anomaly type. Priority is derived from impact
(annualized cost) so the list is ordered by what matters most, not detection
order.
"""
from __future__ import annotations

from ..trace import Trace

# Annual cost multiplier per anomaly type — how a single detected issue maps to
# dollars per year. Used to prioritize.
ANNUAL_MULTIPLIER = {
    "duplicate_charge": 1.0,       # one extra charge this month (recoverable)
    "subscription_price_hike": 12.0,  # the delta compounds every month
    "large_one_off": 1.0,          # one-time
    "subscription_creep": 12.0,    # recurring from here on
    "category_spend_spike": 1.0,   # one month
    "lapsed_subscription_still_billing": 12.0,  # keeps billing monthly
    "missing_invoice": 0.0,        # vendor went quiet — not a cash drain; confirm only
}

RECOMMENDATION_TEXT = {
    "duplicate_charge": "Dispute or request a refund for the duplicate charge.",
    "subscription_price_hike": "Review the price change; downgrade or renegotiate if unplanned.",
    "large_one_off": "Confirm this was an approved, one-time expense.",
    "subscription_creep": "Decide whether these new subscriptions are still needed.",
    "category_spend_spike": "Investigate what drove the spike and set a budget guardrail.",
    "lapsed_subscription_still_billing": "Cancel the redundant subscription.",
    "missing_invoice": "Verify the vendor is no longer billing and not just missing an invoice.",
}


def _amount_for(candidate: dict) -> float:
    """Best monthly-dollar figure for a candidate, preferring an explicit amount.

    Some detections (subscription creep, missing invoice) don't carry a single
    row amount, so we read the vendor's latest monthly total from the context
    the investigate stage attached. Falls back to 0 only if there is truly no
    dollar figure anywhere.
    """
    explicit = candidate.get("amount")
    if explicit is not None:
        return float(explicit)

    history = (candidate.get("context") or {}).get("vendor_history") or []
    if history:
        return float(history[-1]["total"])
    return 0.0


def generate_recommendations(trace: Trace, candidates: list[dict]) -> list[dict]:
    action = trace.start("generate_recommendations", candidate_count=len(candidates))

    recommendations = []
    for c in candidates:
        atype = c["type"]
        amount = _amount_for(c)
        annual_cost = amount * ANNUAL_MULTIPLIER.get(atype, 1.0)
        recommendations.append({
            "type": atype,
            "vendor": c["vendor"],
            "date": c.get("date"),
            "amount": round(amount, 2),
            "annual_cost_estimate": round(annual_cost, 2),
            "recommendation": RECOMMENDATION_TEXT.get(atype, "Review this anomaly."),
        })

    recommendations.sort(key=lambda r: r["annual_cost_estimate"], reverse=True)
    action.finish({"recommendation_count": len(recommendations)})
    return recommendations
