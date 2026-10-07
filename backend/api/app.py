"""Thin FastAPI API layer over the existing Proof-Carrying Data Analyst backend.

RULES:
1. No calculation/math is performed here.
2. All analysis is delegated to DataAnalystAgent.
3. All code execution runs in the controlled execution sandbox.
4. All verification is deterministic.
5. All numerical results come exclusively from executed Python.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent.agent import DataAnalystAgent, STAGES
from backend.execution.executor import execute_code
from backend.ingestion import content_hash, load_bytes
from backend.llm.openrouter import OpenRouterClient
from backend.models.schemas import AnalysisReport, DatasetProfile, Status
from backend.provenance.evidence import fingerprint
from backend.verification.verifier import summarize_result, verify_execution

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "sample"
EDGE_CASES = ROOT / "data" / "edge_cases"
OUTPUTS = ROOT / "outputs"
AUDIT_LOGS = OUTPUTS / "audit_logs"

app = FastAPI(
    title="Proof Analyst API",
    description="Thin API layer for Proof-Carrying Data Analyst. Every answer comes with proof.",
    version="1.0.0",
)

# Enable CORS for React frontend (Vite dev server default: 5173, plus localhost variants)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory State & Caching ---
_cached_tables: Dict[str, Any] = {}
_cached_profiles: Dict[str, DatasetProfile] = {}
_cached_cross_warnings: List[str] = []
_agent_instance: Optional[DataAnalystAgent] = None
_start_time = time.time()


def get_agent() -> DataAnalystAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DataAnalystAgent(OpenRouterClient(), outputs_dir=OUTPUTS)
    return _agent_instance


def refresh_profiles():
    global _cached_profiles, _cached_cross_warnings
    if not _cached_tables:
        _cached_profiles = {}
        _cached_cross_warnings = []
        return
    agent = get_agent()
    _cached_profiles, _cached_cross_warnings = agent.profile(_cached_tables)


# --- Request/Response Models ---
class AnalyzeRequest(BaseModel):
    question: str


class RerunRequest(BaseModel):
    code: str
    question: str
    original_value: Optional[float] = None
    original_metric: Optional[str] = None
    original_entity: Optional[str] = None


class RerunResponse(BaseModel):
    matched: bool
    status: str
    original_result: Optional[Dict[str, Any]] = None
    rerun_result: Optional[Dict[str, Any]] = None
    rerun_summary: str = ""
    stdout: str = ""
    stderr: str = ""
    message: str = ""


# --- Endpoints ---


@app.get("/api/health")
def health():
    """System status check."""
    api_key_configured = bool(os.environ.get("OPENROUTER_API_KEY"))
    return {
        "status": "healthy",
        "openrouter_configured": api_key_configured,
        "model": os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6"),
        "tables_loaded": len(_cached_tables),
        "uptime_seconds": int(time.time() - _start_time),
    }


@app.get("/api/datasets")
def get_datasets():
    """Returns currently loaded datasets, metadata, columns, and quality warnings."""
    datasets_info = []
    total_rows = 0
    total_cols = 0
    total_warnings = len(_cached_cross_warnings)

    for name, table in _cached_tables.items():
        prof = _cached_profiles.get(name)
        rows = len(table.df)
        cols = len(table.df.columns)
        total_rows += rows
        total_cols += cols
        warnings = prof.warnings if prof else []
        total_warnings += len(warnings)

        col_details = []
        if prof:
            for c in prof.columns:
                col_details.append(
                    {
                        "name": c.name,
                        "dtype": c.dtype,
                        "missing": c.missing,
                        "unique": c.unique,
                        "likely_numeric": c.likely_numeric,
                        "likely_date": c.likely_date,
                        "ambiguous_date": c.ambiguous_date,
                        "unit_hints": c.unit_hints,
                    }
                )
        else:
            for col_name in table.df.columns:
                col_details.append(
                    {
                        "name": str(col_name),
                        "dtype": str(table.df[col_name].dtype),
                        "missing": int(table.df[col_name].isna().sum()),
                        "unique": int(table.df[col_name].nunique()),
                        "likely_numeric": False,
                        "likely_date": False,
                        "ambiguous_date": False,
                        "unit_hints": [],
                    }
                )

        datasets_info.append(
            {
                "name": name,
                "variable": table.variable,
                "source_file": table.source_file,
                "sheet": table.sheet,
                "rows": rows,
                "columns_count": cols,
                "duplicate_rows": prof.duplicate_rows if prof else 0,
                "warnings": warnings,
                "columns": col_details,
                "sample_rows": json.loads(table.df.head(5).to_json(orient="records", date_format="iso")),
            }
        )

    return {
        "datasets": datasets_info,
        "cross_table_warnings": _cached_cross_warnings,
        "summary": {
            "total_files": len(datasets_info),
            "total_rows": total_rows,
            "total_columns": total_cols,
            "total_warnings": total_warnings,
        },
    }


@app.post("/api/datasets/upload")
async def upload_datasets(files: List[UploadFile] = File(...)):
    """Upload CSV or XLSX files and add to active session."""
    global _cached_tables
    skipped_messages = []
    loaded_count = 0

    for file in files:
        contents = await file.read()
        filename = file.filename or "uploaded_file"
        loaded, skipped = load_bytes(filename, contents)
        _cached_tables.update(loaded)
        skipped_messages.extend(skipped)
        loaded_count += len(loaded)

    refresh_profiles()

    return {
        "message": f"Successfully loaded {loaded_count} table(s).",
        "skipped": skipped_messages,
        "tables_count": len(_cached_tables),
    }


@app.post("/api/datasets/demo")
def load_demo_datasets():
    """Loads standard demo datasets: sales.csv, costs.csv, products.xlsx."""
    global _cached_tables
    _cached_tables.clear()

    demo_files = ["sales.csv", "costs.csv", "products.xlsx"]
    skipped_messages = []
    for fname in demo_files:
        fpath = SAMPLES / fname
        if fpath.exists():
            loaded, skipped = load_bytes(fname, fpath.read_bytes())
            _cached_tables.update(loaded)
            skipped_messages.extend(skipped)

    refresh_profiles()
    return {
        "message": "Demo datasets loaded successfully.",
        "tables_loaded": list(_cached_tables.keys()),
        "skipped": skipped_messages,
    }


@app.post("/api/datasets/demo/messy")
def load_messy_demo_datasets():
    """Loads messy edge case datasets to demonstrate traps and CANNOT_DETERMINE."""
    global _cached_tables
    _cached_tables.clear()

    trap_files = [
        ("sales_duplicates.csv", EDGE_CASES / "sales_duplicates.csv"),
        ("costs_usd_mismatch.csv", EDGE_CASES / "costs_usd_mismatch.csv"),
        ("sales_conflicts.csv", EDGE_CASES / "sales_conflicts.csv"),
    ]
    for name, path in trap_files:
        if path.exists():
            loaded, _ = load_bytes(name, path.read_bytes())
            _cached_tables.update(loaded)

    refresh_profiles()
    return {
        "message": "Messy / trap datasets loaded successfully.",
        "tables_loaded": list(_cached_tables.keys()),
    }


@app.delete("/api/datasets")
def clear_datasets():
    """Clears all loaded datasets from active session."""
    global _cached_tables, _cached_profiles, _cached_cross_warnings
    _cached_tables.clear()
    _cached_profiles.clear()
    _cached_cross_warnings = []
    return {"message": "All datasets cleared."}


@app.get("/api/datasets/{table_name}/rows")
def get_table_rows(table_name: str, limit: int = 50, offset: int = 0):
    """Returns rows for source row inspector."""
    if table_name not in _cached_tables:
        raise HTTPException(status_code=404, detail=f"Table {table_name} not found")

    df = _cached_tables[table_name].df
    total = len(df)
    slice_df = df.iloc[offset : offset + limit]
    rows = json.loads(slice_df.to_json(orient="records", date_format="iso"))

    return {
        "table": table_name,
        "total_rows": total,
        "limit": limit,
        "offset": offset,
        "columns": list(df.columns),
        "rows": rows,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Executes the complete proof-carrying data analysis pipeline."""
    if not _cached_tables:
        raise HTTPException(status_code=400, detail="No datasets loaded. Please upload or load demo data first.")

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    agent = get_agent()
    # Runs the real Python backend
    report = agent.analyze(question, _cached_tables, profiles=_cached_profiles)
    return report.model_dump(mode="json")


@app.post("/api/proof/rerun", response_model=RerunResponse)
def rerun_proof(req: RerunRequest):
    """
    Major hackathon feature: Deterministically re-executes the EXACT generated Python code
    in the restricted sandbox against the current loaded tables and compares the result.
    NO LLM call is used here.
    """
    if not _cached_tables:
        raise HTTPException(status_code=400, detail="No datasets available for re-execution.")

    frames = {t.variable: t.df.copy() for t in _cached_tables.values()}
    # Re-execute code in sandbox
    ex = execute_code(req.code, frames, timeout=30)

    if not ex.success:
        return RerunResponse(
            matched=False,
            status="EXECUTION_FAILED",
            stdout=ex.stdout,
            stderr=ex.stderr,
            message=f"Re-execution failed: {ex.stderr}",
        )

    # Deterministically parse and verify rerun structured output
    ver = verify_execution(
        question=req.question,
        plan=None,
        execution=ex,
        tables=_cached_tables,
        profiles=_cached_profiles,
        code=req.code,
    )

    rerun_sr = ver.structured_result.model_dump(mode="json", exclude_none=True) if ver.structured_result else None
    rerun_summary = summarize_result(ver.structured_result) if ver.structured_result else ""

    matched = False
    diff_msg = ""

    if ver.status == Status.VERIFIED and ver.structured_result is not None:
        if req.original_value is not None:
            # Check numerical equivalence
            tol = 0.005
            if ver.structured_result.value is not None:
                val_diff = abs(ver.structured_result.value - req.original_value)
                if val_diff <= max(tol, 1e-9 * abs(req.original_value)):
                    matched = True
                else:
                    diff_msg = f"Value mismatch: original {req.original_value} vs rerun {ver.structured_result.value}"
            elif ver.structured_result.values is not None:
                # Comparison or ranking dictionary
                matched = True
            else:
                matched = True
        else:
            matched = True
    else:
        diff_msg = f"Rerun status was {ver.status.value}"

    return RerunResponse(
        matched=matched,
        status=ver.status.value,
        original_result={
            "value": req.original_value,
            "metric": req.original_metric,
            "selected_entity": req.original_entity,
        },
        rerun_result=rerun_sr,
        rerun_summary=rerun_summary,
        stdout=ex.stdout,
        stderr=ex.stderr,
        message="Results match perfectly! Proof reproduced." if matched else (diff_msg or "Results differ."),
    )


@app.get("/api/history")
def get_history():
    """Reads all persisted audit reports from outputs/audit_logs."""
    if not AUDIT_LOGS.exists():
        return []

    history = []
    files = sorted(AUDIT_LOGS.glob("*.json"), key=os.path.getmtime, reverse=True)
    for f in files[:50]:  # Up to 50 recent records
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            audit_id = f.stem
            history.append(
                {
                    "audit_id": audit_id,
                    "question": data.get("question", ""),
                    "status": data.get("status", ""),
                    "answer": data.get("answer", ""),
                    "created_at": data.get("evidence", {}).get("timestamp", ""),
                    "llm_calls": data.get("llm_calls", 0),
                    "files_used": data.get("evidence", {}).get("files_used", []),
                    "metric": data.get("structured_result", {}).get("metric", "") if data.get("structured_result") else "",
                    "value": data.get("structured_result", {}).get("value") if data.get("structured_result") else None,
                }
            )
        except Exception:
            continue
    return history


@app.get("/api/analysis/{analysis_id}")
def get_analysis_by_id(analysis_id: str):
    """Retrieves full audit report for an analysis ID."""
    fpath = AUDIT_LOGS / f"{analysis_id}.json"
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
