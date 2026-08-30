"""Measure anomaly-detection precision/recall against the planted ground truth.

Run: .venv/Scripts/python.exe -m tests.test_detection
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from backend.pipeline import run_pipeline

DATA = Path(__file__).resolve().parent.parent / "data"


def _load_ground_truth() -> list[dict]:
    gt = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))
    return gt["anomalies"]


def _id(anomaly: dict) -> tuple:
    """A type+date key that maps a detected candidate to a planted one."""
    return (anomaly["type"], anomaly.get("date"))


def main() -> None:
    result = run_pipeline()
    assert result["ok"], result.get("error")

    detected = result["anomalies"]
    planted = _load_ground_truth()

    # Map each planted anomaly to a detector type + expected month.
    expected_keys = {
        "dup-charge-aws": ("duplicate_charge", "2025-06-15"),
        "price-hike-notion": ("subscription_price_hike", "2025-07"),
        "large-oneoff-consulting": ("large_one_off", "2025-07-10"),
        "subscription-creep": ("subscription_creep", "2025-07"),
        "spend-spike-marketing": ("category_spend_spike", "2025-07"),
        "missing-invoice-freelancer": ("missing_invoice", "2025-05"),
        # "lapsed-subscription-canva" is NOT expected: it needs vendor context
        # and is caught by the investigate stage in step 4.
    }

    detected_keys = {_id(a) for a in detected}

    tp = 0
    print("Per-anomaly detection:")
    for planted_a in planted:
        key = expected_keys.get(planted_a["id"])
        if key is None:
            print(f"  SKIP  {planted_a['id']}  (not a detect-stage target)")
            continue
        ok = key in detected_keys
        tp += ok
        print(f"  {'HIT ' if ok else 'MISS'}  {planted_a['id']}  ->  {key}")

    fp = len(detected) - tp
    fn = len(expected_keys) - tp

    precision = tp / len(detected) if detected else 0.0
    recall = tp / len(expected_keys) if expected_keys else 0.0

    print(f"\nDetected {len(detected)} candidates, planted {len(expected_keys)}.")
    print(f"True positives: {tp}, false positives: {fp}, false negatives: {fn}")
    print(f"Precision: {precision:.2%}  Recall: {recall:.2%}")

    # Detection is "good enough" if it surfaces most of the planted anomalies.
    assert recall >= 0.75, f"recall too low: {recall:.2%}"


if __name__ == "__main__":
    main()
