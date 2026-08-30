"""Verify the planted anomalies actually exist in the generated CSV.

Run: .venv/Scripts/python.exe -m tests.verify_ground_truth
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load_rows() -> list[dict]:
    with (DATA / "transactions.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows = load_rows()
    gt = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))
    print(f"total rows: {len(rows)}")

    checks = {
        "duplicate AWS 512.64 on 2025-06-15": sum(
            1
            for r in rows
            if r["vendor"] == "AWS"
            and r["amount"] == "512.64"
            and r["date"] == "2025-06-15"
        )
        == 2,
        "Notion price hike 48 -> 192": {float(r["amount"]) for r in rows if r["vendor"] == "Notion"}
        == {48.0, 192.0},
        "consulting 12000 one-off": sum(
            1 for r in rows if r["amount"] == "12000.00"
        )
        == 1,
        "subscription creep vendors": set(
            r["vendor"] for r in rows if r["vendor"] in ("Dropbox", "Calendly", "Trello")
        )
        == {"Dropbox", "Calendly", "Trello"},
        "Canva still billing next to Figma": any(r["vendor"] == "Canva Pro" for r in rows)
        and any(r["vendor"] == "Figma" for r in rows),
        "freelancer appears then stops": sum(
            1 for r in rows if r["vendor"] == "Freelancer - Design"
        )
        > 0,
    }

    july = sum(
        float(r["amount"])
        for r in rows
        if r["category"] == "Marketing" and r["date"].startswith("2025-07")
    )
    june = sum(
        float(r["amount"])
        for r in rows
        if r["category"] == "Marketing" and r["date"].startswith("2025-06")
    )
    checks["marketing July spike over June"] = july > june * 1.5
    print(f"marketing June total: {june:.2f}, July total: {july:.2f}")

    all_ok = True
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        all_ok = all_ok and ok

    print(f"\n{len(gt['anomalies'])} anomalies in ground_truth.json")
    print("ALL PLANTED ANOMALIES PRESENT" if all_ok else "MISSING ANOMALIES — investigate")


if __name__ == "__main__":
    main()
