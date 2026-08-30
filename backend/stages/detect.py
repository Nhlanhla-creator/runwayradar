"""Stage 2: anomaly detection.

Pure rule-based detectors over the parsed rows. Each detector returns a list of
candidate anomalies with a human-readable reason and the evidence it relied on,
so the trace stays inspectable. No LLM, no external calls — deterministic.

The six rule-detected anomaly types:
  duplicate_charge           identical (vendor, date, amount) appearing twice+
  subscription_price_hike    recurring vendor's monthly total jumps >= 1.5x
  large_one_off              one-off amount far above that vendor's typical size
  subscription_creep         recurring vendors that first appear only recently
  category_spend_spike       a category's monthly total spikes vs. its baseline
  missing_invoice            a recurring vendor that stopped appearing early

The seventh planted type (lapsed_subscription_still_billing) is deliberately
NOT caught here: it needs vendor-context that the investigate stage (step 4)
pulls in. This is an intentional, documented limitation, not an oversight.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median

from ..trace import Trace

# Tuning knobs, kept here so they are easy to find and justify in the demo.
PRICE_HIKE_RATIO = 1.5
ONE_OFF_MEDIAN_MULTIPLE = 3.0
SPIKE_RATIO = 2.5        # a category must jump 2.5x its baseline to be a spike
SPIKE_MIN_DELTA = 500.0  # ...and by at least $500 in absolute terms
CREEP_MONTHS = 2  # a vendor is "creep" if it first appears in the last N months


def _parse(rows: list[dict]) -> list[dict]:
    parsed = []
    for r in rows:
        parsed.append({
            "date": r["date"],
            "month": r["date"][:7],
            "vendor": r["vendor"],
            "category": r["category"],
            "amount": float(r["amount"]),
            "recurring": r["recurring"].strip().lower() == "true",
        })
    return parsed


def _detect_duplicates(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["vendor"], r["date"], r["amount"])].append(r)

    found = []
    for (vendor, date, amount), matches in groups.items():
        if len(matches) >= 2:
            found.append({
                "type": "duplicate_charge",
                "vendor": vendor,
                "date": date,
                "amount": amount,
                "category": matches[0]["category"],
                "reason": (
                    f"{vendor} was charged {amount:.2f} {len(matches)} times "
                    f"on {date} — identical vendor, date, and amount."
                ),
                "evidence": [m["date"] for m in matches],
            })
    return found


def _detect_price_hikes(rows: list[dict]) -> list[dict]:
    recurring = [r for r in rows if r["recurring"]]
    by_vendor: dict[str, list[dict]] = defaultdict(list)
    for r in recurring:
        by_vendor[r["vendor"]].append(r)

    found = []
    for vendor, vendor_rows in by_vendor.items():
        monthly: dict[str, float] = defaultdict(float)
        for r in vendor_rows:
            monthly[r["month"]] += r["amount"]
        ordered = sorted(monthly.items())
        for (prev_m, prev_total), (cur_m, cur_total) in zip(ordered, ordered[1:]):
            if prev_total <= 0:
                continue
            if cur_total >= prev_total * PRICE_HIKE_RATIO:
                found.append({
                    "type": "subscription_price_hike",
                    "vendor": vendor,
                    "date": cur_m,
                    "amount": round(cur_total - prev_total, 2),
                    "reason": (
                        f"{vendor} monthly total rose from {prev_total:.2f} "
                        f"({prev_m}) to {cur_total:.2f} ({cur_m}) — a "
                        f"{cur_total / prev_total:.1f}x jump."
                    ),
                    "evidence": {"from": prev_total, "to": cur_total},
                })
    return found


def _detect_large_one_offs(rows: list[dict]) -> list[dict]:
    one_offs = [r for r in rows if not r["recurring"]]
    by_vendor: dict[str, list[float]] = defaultdict(list)
    for r in one_offs:
        by_vendor[r["vendor"]].append(r["amount"])

    found = []
    for vendor, amounts in by_vendor.items():
        if len(amounts) < 3:
            continue
        baseline = median(amounts)
        if baseline <= 0:
            continue
        for r in one_offs:
            if r["vendor"] != vendor:
                continue
            if r["amount"] >= baseline * ONE_OFF_MEDIAN_MULTIPLE and r["amount"] >= 2000:
                found.append({
                    "type": "large_one_off",
                    "vendor": vendor,
                    "category": r["category"],
                    "date": r["date"],
                    "amount": r["amount"],
                    "reason": (
                        f"{vendor} charged {r['amount']:.2f} on {r['date']}, "
                        f"well above its typical ~{baseline:.0f} — "
                        f"{r['amount'] / baseline:.1f}x the median."
                    ),
                    "evidence": {"vendor_median": round(baseline, 2)},
                })
    return found


def _detect_subscription_creep(rows: list[dict]) -> list[dict]:
    recurring = [r for r in rows if r["recurring"]]
    months = sorted({r["month"] for r in recurring})
    if len(months) <= CREEP_MONTHS:
        return []
    late_months = set(months[-CREEP_MONTHS:])

    first_month: dict[str, str] = {}
    for r in recurring:
        cur = first_month.get(r["vendor"])
        if cur is None or r["month"] < cur:
            first_month[r["vendor"]] = r["month"]

    found = []
    for vendor, first in first_month.items():
        if first in late_months:
            found.append({
                "type": "subscription_creep",
                "vendor": vendor,
                "date": first,
                "amount": None,
                "reason": (
                    f"{vendor} is a new recurring charge first seen {first} — "
                    f"check whether this subscription is still wanted."
                ),
                "evidence": {"first_seen": first},
            })
    return found


def _detect_category_spikes(rows: list[dict]) -> list[dict]:
    by_cat_month: dict[tuple, float] = defaultdict(float)
    for r in rows:
        by_cat_month[(r["category"], r["month"])] += r["amount"]

    by_cat: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (cat, month), total in by_cat_month.items():
        by_cat[cat].append((month, total))

    found = []
    for cat, series in by_cat.items():
        ordered = sorted(series)
        if len(ordered) < 2:
            continue
        # Baseline = median of all months except the candidate spike month,
        # so a single planted spike can't inflate its own baseline (unlike a
        # simple prev-month ratio). This kills the 1.5x-on-$150 noise.
        totals = [total for _, total in ordered]
        for i, (cur_m, cur_total) in enumerate(ordered):
            others = [t for j, t in enumerate(totals) if j != i]
            baseline = median(others) if others else 0.0
            if baseline <= 0:
                continue
            if cur_total >= baseline * SPIKE_RATIO and (cur_total - baseline) >= SPIKE_MIN_DELTA:
                found.append({
                    "type": "category_spend_spike",
                    "vendor": cat,
                    "date": cur_m,
                    "amount": round(cur_total, 2),
                    "reason": (
                        f"{cat} spending was {cur_total:.2f} in {cur_m} vs. a "
                        f"median {baseline:.2f} across other months — a "
                        f"{cur_total / baseline:.1f}x jump."
                    ),
                    "evidence": {"baseline": round(baseline, 2), "actual": round(cur_total, 2)},
                })
    return found


def _detect_missing_invoices(rows: list[dict]) -> list[dict]:
    recurring = [r for r in rows if r["recurring"]]
    months = sorted({r["month"] for r in rows})
    last_month = months[-1]

    by_vendor: dict[str, list[str]] = defaultdict(list)
    for r in recurring:
        by_vendor[r["vendor"]].append(r["month"])

    found = []
    for vendor, vendor_months in by_vendor.items():
        distinct = sorted(set(vendor_months))
        if len(distinct) < 3:
            continue
        if distinct[-1] < last_month:
            found.append({
                "type": "missing_invoice",
                "vendor": vendor,
                "date": distinct[-1],
                "amount": None,
                "reason": (
                    f"{vendor} billed monthly through {distinct[-1]} then "
                    f"stopped — a recurring cost that has gone quiet."
                ),
                "evidence": {"last_seen": distinct[-1], "months": distinct},
            })
    return found


def _reconcile(candidates: list[dict]) -> list[dict]:
    """Suppress generic findings that a more specific root cause already explains.

    A duplicate charge (e.g. AWS charged twice) also makes that vendor's monthly
    total jump, so it would otherwise ALSO be reported as a price hike and as a
    category spike — three cards for one problem. Same for a large one-off
    making its category's month look like a spike. Keep the specific card, drop
    the generic ones it explains.
    """
    explained_vendor_months = {
        (c["vendor"], c["date"][:7]) for c in candidates if c["type"] == "duplicate_charge"
    }
    explained_category_months = {
        (c["category"], c["date"][:7])
        for c in candidates
        if c["type"] in ("large_one_off", "duplicate_charge")
    }

    kept = []
    for c in candidates:
        if c["type"] == "subscription_price_hike":
            if (c["vendor"], c["date"][:7]) in explained_vendor_months:
                continue
        if c["type"] == "category_spend_spike":
            if (c["vendor"], c["date"][:7]) in explained_category_months:
                continue
        kept.append(c)
    return kept


def detect_anomalies(trace: Trace, rows: list[dict]) -> list[dict]:
    action = trace.start("detect_anomalies", row_count=len(rows))
    parsed = _parse(rows)

    detectors = [
        ("duplicate_charge", _detect_duplicates),
        ("subscription_price_hike", _detect_price_hikes),
        ("large_one_off", _detect_large_one_offs),
        ("subscription_creep", _detect_subscription_creep),
        ("category_spend_spike", _detect_category_spikes),
        ("missing_invoice", _detect_missing_invoices),
    ]

    candidates: list[dict] = []
    counts: dict[str, int] = {}
    for name, fn in detectors:
        found = fn(parsed)
        counts[name] = len(found)
        candidates.extend(found)

    candidates = _reconcile(candidates)
    action.finish({"candidate_count": len(candidates), "by_type": counts})
    return candidates
