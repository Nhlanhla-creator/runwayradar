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
- `data/examples/` — additional sanitized CSVs available from the dashboard's
  **Try an example** selector: bank export, accounting export, alternate date
  formats, and a small startup dataset.

## Uploading financial data

Open the dashboard and choose **Upload CSV**. RunwayRadar accepts common export
header names and normalizes them into the canonical fields used by the agent:

- Date: `date`, `transaction date`, `posted`, or `posted date`
- Vendor: `vendor`, `description`, `merchant`, or `payee`
- Category: `category`, `type`, or `expense type`
- Amount: `amount`, `debit`, `withdrawal`, `value`, or `transaction amount`
- `recurring` is optional and defaults to `false`

Amounts may include dollar signs, commas, spaces, and accounting negatives such
as `(45.00)`. Dates may be ISO (`2025-03-05`) or common slash/dash formats such
as `03/05/2025`. After upload, the same six-stage pipeline runs against the
uploaded rows, and the dashboard, charts, flags, trace, and questions all use
that current dataset. Use **Reset to sample** to return to the bundled data.

The upload path intentionally rejects files missing a recognizable date,
vendor, category, or amount column with a clear error instead of silently
producing incorrect financial results.

