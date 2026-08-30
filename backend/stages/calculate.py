"""Stage 4: calculate hard numbers — burn rate, runway, anomaly cost impact.

Formulas (shown here so they can be sanity-checked):

  monthly_burn[m]   = sum of every transaction amount in month m
  avg_monthly_burn  = total spend over the whole period / number of months
  recent_monthly_burn = mean of the last RUNWAY_LOOKBACK_MONTHS months
                       (burn changes over time; runway should use the recent
                       rate, not the all-time average)
  runway_months     = starting_cash / recent_monthly_burn
  anomaly_cost_impact = sum of the flagged anomalies' monthly amounts, as a
                        fraction of recent_monthly_burn (annualized it shows
                        how much runway the flagged items are draining)

The dataset has no cash-balance column, so starting_cash is an explicit,
documented assumption rather than something silently inferred.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ..trace import Trace

# Assumed cash on hand, in dollars. The synthetic dataset contains only spend
# records, so runway needs an external balance. This is the one number a user
# would supply; it is a constant here for a reproducible demo.
STARTING_CASH = 50_000.00

RUNWAY_LOOKBACK_MONTHS = 3


def calculate_metrics(trace: Trace, rows: list[dict], candidates: list[dict]) -> dict:
    action = trace.start("calculate_metrics", starting_cash=STARTING_CASH)

    monthly: dict[str, float] = defaultdict(float)
    for r in rows:
        monthly[r["date"][:7]] += float(r["amount"])

    months = sorted(monthly)
    if not months:
        action.finish({"error": "no data"})
        return {}

    total_spend = sum(monthly.values())
    avg_monthly_burn = total_spend / len(months)

    recent_months = months[-RUNWAY_LOOKBACK_MONTHS:]
    recent_monthly_burn = mean(monthly[m] for m in recent_months)

    runway_months = STARTING_CASH / recent_monthly_burn if recent_monthly_burn > 0 else 0.0

    # Anomaly cost impact: recurring flagged amounts count monthly; one-off
    # flagged amounts count once. Summed and annualized as a fraction of burn.
    recurring_impact = 0.0
    oneoff_impact = 0.0
    recurring_types = {
        "duplicate_charge",
        "subscription_price_hike",
        "subscription_creep",
        "lapsed_subscription_still_billing",
        "missing_invoice",
    }
    for c in candidates:
        amt = c.get("amount")
        if amt is None:
            history = (c.get("context") or {}).get("vendor_history") or []
            amt = float(history[-1]["total"]) if history else 0.0
        amt = float(amt)
        if c["type"] in recurring_types:
            recurring_impact += amt
        else:
            oneoff_impact += amt

    monthly_impact = recurring_impact + (oneoff_impact / 12.0)
    impact_fraction = monthly_impact / recent_monthly_burn if recent_monthly_burn > 0 else 0.0

    metrics = {
        "months_covered": len(months),
        "total_spend": round(total_spend, 2),
        "avg_monthly_burn": round(avg_monthly_burn, 2),
        "recent_monthly_burn": round(recent_monthly_burn, 2),
        "starting_cash": round(STARTING_CASH, 2),
        "runway_months": round(runway_months, 1),
        "anomaly_cost_impact": {
            "recurring_monthly": round(recurring_impact, 2),
            "oneoff_total": round(oneoff_impact, 2),
            "monthly_equivalent": round(monthly_impact, 2),
            "fraction_of_burn": round(impact_fraction, 4),
        },
        "monthly_burn": {m: round(t, 2) for m, t in monthly.items()},
    }
    action.finish(metrics)
    return metrics
