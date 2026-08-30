# RunwayRadar

An agentic finance copilot: it reads a transactions dataset, detects anomalies,
investigates each candidate, calculates burn rate and runway, and flags the top
issues for action — with a visible, step-by-step trace.

> Built for the Global AI Hackathon, Agentic Finance track. Sanitized/synthetic
> data only. No trading or lending advice.

## Requirements

- Windows with Python 3.14 (`py -3`)
- No Node.js, no API keys needed

## Setup (fresh clone)

```bat
py -3 -m venv .venv
.venv\Scripts\activate
py -3 -m pip install -r requirements.txt
py -3 -m backend.data_generator
py -3 -m pytest
py -3 -m uvicorn backend.main:app --port 8000
```

Then open <http://localhost:8000/>.

> Use `py -3` on Windows — the bare `python` command is often a Microsoft Store
> alias that opens the store instead of running Python.

## Data

- `data/transactions.csv` — synthetic transactions. Regenerate anytime with
  `py -3 -m backend.data_generator` (deterministic seed, 181 rows).
- `data/ground_truth.json` — planted-anomaly answer key for testing only; never
  shown in the UI. Verify the anomalies are actually present in the CSV with
  `py -3 -m tests.verify_ground_truth`.
