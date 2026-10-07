import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from backend.models.schemas import AnalysisReport, Evidence
from backend.verification import validation as V
from backend.verification.verifier import summarize_result

_OPS = {"merge": "join (merge)", "groupby": "group by", "drop_duplicates": "exact duplicate rows removed",
        "dropna": "rows with missing values excluded", "fillna": "missing values filled (imputation)",
        "to_datetime": "dates parsed", "idxmax": "maximum selected", "idxmin": "minimum selected",
        "mean": "average computed", "sum": "sum computed", "median": "median computed"}


def fingerprint(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()[:16]


def build_evidence(question, plan, code, execution, verification, tables, profiles=None, retrieval=None) -> Evidence:
    """Everything here is derived from the code that actually ran and the data actually loaded - never from model claims."""
    used, cols = V.code_usage(code, tables)
    ops = [label for key, label in _OPS.items() if re.search(rf"\b{key}\b", code)]
    derived = [f"derived column: {d}" for d in V.extract_derivations(code)]
    actions, dq_warn, records = [], [], []
    for n in used:
        p = profiles[n] if profiles else None
        if not p:
            continue
        dq_warn += [f"{n}: {w}" for w in p.warnings]
        records.append(V.dq_record(n, tables[n].df, code, cols.get(n, [])))
        if p.duplicate_rows and V.handles_duplicates(code):
            actions.append(f"{n}: {p.duplicate_rows} exact duplicate rows dropped (rule: exact duplicates are removed before calculation)")
        for c in cols.get(n, []):
            cp = next((x for x in p.columns if x.name == c), None)
            if cp and cp.missing and V.handles_missing(code):
                how = "imputed with fillna" if "fillna" in code else "excluded with dropna"
                actions.append(f"{n}.{c}: {cp.missing} missing values {how}")
    sr = verification.structured_result if verification else None
    return Evidence(
        question=question, timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        files_used=sorted({tables[n].source_file for n in used}),
        tables_used=list(used), sheets_used=[f"{tables[n].source_file}::{tables[n].sheet}" for n in used if tables[n].sheet],
        columns_used=cols, retrieval=retrieval or [], planned_operations=list(plan.operations) if plan else [],
        filters=V.extract_filters(code), joins=V.extract_joins(code), transformations=derived + ops,
        data_quality_warnings=dq_warn, data_quality_actions=actions, data_quality_records=records, structured_result=sr,
        result_summary=summarize_result(sr) if sr else "",
        code=code, code_sha256=hashlib.sha256(code.encode()).hexdigest(),
        execution_status="SUCCESS" if execution and execution.success else "FAILED",
        execution_output=(execution.stdout if execution else ""),
        verification_status=verification.status.value if verification else "",
        data_fingerprints={n: fingerprint(tables[n].df) for n in used},
    )


def save_audit(report: AnalysisReport, out_dir) -> str:
    out = Path(out_dir)
    for sub in ("generated_code", "execution_results", "audit_logs"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if report.code:
        (out / "generated_code" / f"{ts}.py").write_text(report.code, encoding="utf-8")
    if report.execution:
        (out / "execution_results" / f"{ts}.json").write_text(report.execution.model_dump_json(indent=2), encoding="utf-8")
    (out / "audit_logs" / f"{ts}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return ts
