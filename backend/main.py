"""RunwayRadar API + static frontend server."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import Body, FastAPI, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import pipeline, qa

app = FastAPI(title="RunwayRadar", version="0.1.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# The dataset the loop currently runs on. None = the bundled sample CSV.
# Kept in a module-level holder so /api/run, /api/ask and /api/upload all
# agree on which data is "current".
_current_rows: list[dict] | None = None
_current_source = "sample"


EXAMPLES_DIR = DATA_DIR / "examples"


def _decode_csv(contents: bytes) -> list[dict]:
    text = contents.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "runwayradar"}


@app.get("/api/run")
def run() -> dict:
    result = pipeline.run_pipeline(_current_rows)
    result["source"] = _current_source
    return result


@app.get("/api/examples")
def examples() -> dict:
    """List the bundled datasets available to explore."""
    files = sorted(EXAMPLES_DIR.glob("*.csv")) if EXAMPLES_DIR.exists() else []
    return {
        "examples": [
            {"id": f.name, "name": f.stem.replace("-", " ").title()}
            for f in files
        ]
    }


@app.post("/api/examples/{example_id}")
def load_example(example_id: str) -> JSONResponse:
    """Load one bundled example through the same path as an upload."""
    global _current_rows, _current_source
    if Path(example_id).name != example_id or not example_id.lower().endswith(".csv"):
        return JSONResponse({"ok": False, "error": "invalid example name"}, status_code=400)
    example_path = EXAMPLES_DIR / example_id
    if not example_path.is_file():
        return JSONResponse({"ok": False, "error": "example not found"}, status_code=404)
    try:
        with example_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        pipeline.validate_rows(rows)
    except (OSError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _current_rows = rows
    _current_source = example_path.name
    result = pipeline.run_pipeline(rows)
    result["source"] = _current_source
    return JSONResponse(result)


@app.post("/api/upload")
async def upload(file: UploadFile) -> JSONResponse:
    global _current_rows, _current_source
    contents = await file.read()
    try:
        rows = _decode_csv(contents)
        pipeline.validate_rows(rows)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    _current_rows = rows
    _current_source = file.filename or "upload"
    result = pipeline.run_pipeline(rows)
    result["source"] = _current_source
    return JSONResponse(result)


@app.post("/api/reset")
def reset() -> dict:
    global _current_rows, _current_source
    _current_rows = None
    _current_source = "sample"
    result = pipeline.run_pipeline(None)
    result["source"] = _current_source
    return result


@app.post("/api/ask")
def ask(body: dict = Body(...)) -> JSONResponse:
    question = body.get("question", "")
    return JSONResponse(qa.answer_question(question, _current_rows))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
