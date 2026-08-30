"""Generate a realistic synthetic transactions dataset with planted anomalies.

Deterministic (fixed seed) so the dataset and its ground-truth answer key are
reproducible from a fresh clone. Public/sanitized data only — no real financial
records, no trading/lending anything.

Outputs:
    data/transactions.csv    - date, vendor, category, amount, recurring
    data/ground_truth.json   - planted-anomaly answer key (testing only)
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "transactions.csv"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"

SEED = 42

START = date(2025, 3, 1)
END = date(2025, 8, 31)

# Categories and the recurring vendors that populate them. Each tuple is
# (vendor, category, monthly_amount, day_of_month, months_active_slice).
# months are indexed 0..5 (Mar..Aug). slice(None) = all six months.
RECURRING = [
    ("Payroll - Alice", "Payroll", 6200.00, 1, slice(None)),
    ("Payroll - Bob", "Payroll", 5400.00, 1, slice(None)),
    ("Office Rent", "Facilities", 2200.00, 1, slice(None)),
    ("Utilities", "Facilities", 152.40, 2, slice(None)),
    ("Internet", "Facilities", 89.00, 2, slice(None)),
    ("Google Workspace", "SaaS", 72.00, 3, slice(None)),
    ("OpenAI", "SaaS", 40.00, 4, slice(None)),
    # Notion starts normal, then a planted price hike lands in months 4-5.
    ("Notion", "SaaS", 48.00, 5, slice(None)),
    ("GitHub", "SaaS", 60.00, 6, slice(None)),
    ("Slack", "SaaS", 200.00, 7, slice(None)),
    ("Figma", "SaaS", 45.00, 9, slice(None)),
    # Canva Pro keeps billing even after the team moved to Figma (planted).
    ("Canva Pro", "SaaS", 12.99, 9, slice(None)),
    ("Adobe CC", "SaaS", 55.00, 10, slice(None)),
    ("AWS", "Cloud", 437.82, 15, slice(None)),
    ("Google Ads", "Marketing", 300.00, 20, slice(None)),
    # Freelancer stops after May -> planted "missing invoice" gap.
    ("Freelancer - Design", "Contractors", 1200.00, 22, slice(0, 3)),
]

# New small subscriptions that only appear late (subscription creep).
CREEP = [
    ("Dropbox", "SaaS", 11.99, 12, 4),  # first charge July (month index 4)
    ("Calendly", "SaaS", 8.99, 14, 4),
    ("Trello", "SaaS", 14.99, 18, 5),   # first charge August
]

# Normal one-off vendors and their typical amount ranges.
ONE_OFFS = [
    ("Staples", "Office Supplies", 40.0, 130.0),
    ("Amazon", "Office Supplies", 25.0, 180.0),
    ("Delta Airlines", "Travel", 220.0, 650.0),
    ("Marriott", "Travel", 380.0, 900.0),
    ("Uber", "Travel", 20.0, 90.0),
    ("Legal - Smith LLP", "Professional Services", 900.0, 1800.0),
    ("Accountant", "Professional Services", 600.0, 950.0),
    ("Consulting - Growth Strategy", "Professional Services", 1200.0, 2200.0),
    ("Client Dinner", "Meals", 80.0, 240.0),
    ("Team Lunch", "Meals", 60.0, 160.0),
    ("WeWork Day Pass", "Facilities", 30.0, 90.0),
    ("Conference Ticket", "Travel", 300.0, 900.0),
]


def _month_dates() -> list[date]:
    """One date per month (the 1st) from Mar..Aug 2025, for slicing."""
    months = []
    d = START
    while d <= END:
        months.append(date(d.year, d.month, 1))
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return months


def _build_rows() -> list[dict]:
    rng = random.Random(SEED)
    months = _month_dates()
    rows: list[dict] = []

    # --- recurring baseline ---
    for vendor, category, amount, day, active in RECURRING:
        start = active.start if active.start is not None else 0
        stop = active.stop if active.stop is not None else len(months)
        for i, month in enumerate(months):
            if i < start or i >= stop:
                continue
            d = date(month.year, month.month, min(day, 28))
            amt = amount
            # Notion price hike in months 4 and 5 (July and August).
            if vendor == "Notion" and i >= 4:
                amt = 192.00
            # small jitter on the AWS baseline so the dataset isn't suspiciously flat
            if vendor == "AWS":
                amt = round(amount + rng.uniform(-25, 40), 2)
            rows.append({
                "date": d.isoformat(),
                "vendor": vendor,
                "category": category,
                "amount": f"{amt:.2f}",
                "recurring": "true",
            })

    # --- subscription creep (late-arriving small subscriptions) ---
    for vendor, category, amount, day, first_month in CREEP:
        for i in range(first_month, len(months)):
            month = months[i]
            d = date(month.year, month.month, min(day, 28))
            rows.append({
                "date": d.isoformat(),
                "vendor": vendor,
                "category": category,
                "amount": f"{amount:.2f}",
                "recurring": "true",
            })

    # --- one-off transactions ---
    for vendor, category, lo, hi in ONE_OFFS:
        count = rng.randint(4, 9)
        for _ in range(count):
            d = START + timedelta(days=rng.randint(0, (END - START).days))
            amt = round(rng.uniform(lo, hi), 2)
            rows.append({
                "date": d.isoformat(),
                "vendor": vendor,
                "category": category,
                "amount": f"{amt:.2f}",
                "recurring": "false",
            })

    # --- planted anomaly: exact duplicate AWS charge ---
    dup_date = date(2025, 6, 15)
    dup_amt = "512.64"
    for _ in range(2):
        rows.append({
            "date": dup_date.isoformat(),
            "vendor": "AWS",
            "category": "Cloud",
            "amount": dup_amt,
            "recurring": "true",
        })

    # --- planted anomaly: marketing category spend spike in July ---
    # One extra one-off Marketing charge in July makes the category total spike
    # vs. the flat $300/mo Google Ads baseline.
    rows.append({
        "date": "2025-07-22",
        "vendor": "Conference Sponsor Slot",
        "category": "Marketing",
        "amount": "900.00",
        "recurring": "false",
    })

    # --- planted anomaly: unusually large one-off consulting charge ---
    rows.append({
        "date": "2025-07-10",
        "vendor": "Consulting - Growth Strategy",
        "category": "Professional Services",
        "amount": "12000.00",
        "recurring": "false",
    })

    # sort chronologically (stable), then by vendor for readable output
    rows.sort(key=lambda r: (r["date"], r["vendor"]))
    return rows


def generate() -> dict:
    rows = _build_rows()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = ["date", "vendor", "category", "amount", "recurring"]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ground_truth = _ground_truth()
    GROUND_TRUTH_PATH.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")

    return {"rows": len(rows), "anomalies": len(ground_truth["anomalies"])}


def _ground_truth() -> dict:
    return {
        "dataset": {
            "seed": SEED,
            "start": START.isoformat(),
            "end": END.isoformat(),
            "note": "Synthetic data for the Agentic Finance track. No real records.",
        },
        "anomalies": [
            {
                "id": "dup-charge-aws",
                "type": "duplicate_charge",
                "vendor": "AWS",
                "date": "2025-06-15",
                "amount": "512.64",
                "signal": "Two rows with identical (vendor, date, amount).",
            },
            {
                "id": "price-hike-notion",
                "type": "subscription_price_hike",
                "vendor": "Notion",
                "date": "2025-07-05",
                "amount": "192.00",
                "prior_amount": "48.00",
                "signal": "Recurring vendor amount jumps 4x month-over-month.",
            },
            {
                "id": "large-oneoff-consulting",
                "type": "large_one_off",
                "vendor": "Consulting - Growth Strategy",
                "date": "2025-07-10",
                "amount": "12000.00",
                "category_baseline": "~1600",
                "signal": "One-off far above the category's typical range (z-score).",
            },
            {
                "id": "subscription-creep",
                "type": "subscription_creep",
                "vendor": "Dropbox + Calendly + Trello",
                "date": "2025-07-01",
                "amount": "35.97",
                "signal": "New small recurring vendors appearing only in the last 2 months.",
            },
            {
                "id": "spend-spike-marketing",
                "type": "category_spend_spike",
                "vendor": "Google Ads (+ one-offs)",
                "date": "2025-07-20",
                "amount": None,
                "signal": "Marketing category monthly total spikes vs. prior-month baseline.",
            },
            {
                "id": "lapsed-subscription-canva",
                "type": "lapsed_subscription_still_billing",
                "vendor": "Canva Pro",
                "date": "2025-08-09",
                "amount": "12.99",
                "signal": "Recurring SaaS overlapping Figma (team migrated), still billing.",
            },
            {
                "id": "missing-invoice-freelancer",
                "type": "missing_invoice",
                "vendor": "Freelancer - Design",
                "date": "2025-06-01",
                "amount": "1200.00",
                "signal": "Recurring contractor stops appearing after May (expected gap).",
            },
        ],
    }


if __name__ == "__main__":
    result = generate()
    print(f"Wrote {result['rows']} rows to {CSV_PATH}")
    print(f"Wrote {result['anomalies']} anomalies to {GROUND_TRUTH_PATH}")
