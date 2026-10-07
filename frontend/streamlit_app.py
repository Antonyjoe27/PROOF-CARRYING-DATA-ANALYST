import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st

from backend.agent.agent import DataAnalystAgent, STAGES
from backend.ingestion import content_hash, load_bytes
from backend.llm.openrouter import OpenRouterClient
from backend.models.schemas import Severity, Status
from backend.verification.verifier import summarize_result

UPLOADS = ROOT / "data" / "uploads"
SAMPLES = ROOT / "data" / "sample"

st.set_page_config(page_title="Proof-Carrying Data Analyst", layout="wide")
st.title("Proof-Carrying Data Analyst")
st.caption("An AI data analyst that proves its answers: executed code, a structured result, deterministic verification and provenance.")

# ---------- 1. upload ----------
st.header("1. Upload datasets")


@st.cache_data(show_spinner=False)
def load_cached(name: str, digest: str, data: bytes):
    """Parsed once per file CONTENT (digest). Changing the file changes the digest and invalidates this entry."""
    return load_bytes(name, data)


@st.cache_resource
def get_agent():
    return DataAnalystAgent(OpenRouterClient())      # holds the per-dataset-version profile cache


files = st.file_uploader("Upload CSV or XLSX files", type=["csv", "xlsx"], accept_multiple_files=True)
st.caption("Supported formats: CSV, XLSX. PDF is not supported yet.")
if st.button("Load sample data (sales.csv, costs.csv, products.xlsx)"):
    st.session_state["sample"] = True
inputs = [(f.name, f.getvalue()) for f in files or []]
if not inputs and st.session_state.get("sample"):
    inputs = [(n, (SAMPLES / n).read_bytes()) for n in ("sales.csv", "costs.csv", "products.xlsx")]
if not inputs:
    st.info("Upload files (or load the sample data) to begin.")
    st.stop()

tables, skipped = {}, []
for name, data in inputs:
    t, sk = load_cached(name, content_hash(data), data)
    tables.update(t)
    skipped += sk
for msg in skipped:
    st.warning(f"Skipped {msg}")
if not tables:
    st.error("No supported datasets could be loaded.")
    st.stop()

try:
    agent = get_agent()
except Exception as e:
    st.error(f"OpenRouter is not configured: {e}")
    st.stop()

# ---------- 2. overview ----------
st.header("2. Dataset overview")
profiles, cross = agent.profile(tables)   # cached per dataset version
for w in cross:
    st.warning(w)
for name, p in profiles.items():
    with st.expander(f"{name} — {p.rows} rows, {len(p.columns)} columns", expanded=False):
        st.write("Columns: " + ", ".join(f"`{c.name}` ({c.dtype})" for c in p.columns))
        for w in p.warnings:
            st.warning(w)
        st.dataframe(tables[name].df.head(5), width="stretch")

# ---------- 3. question ----------
st.header("3. Ask a question")
question = st.text_input("Ask a question about your data...", placeholder="Which product generated the highest profit?")
if st.button("Analyze", type="primary", disabled=not question.strip()):
    st.session_state["report"] = None
    st.subheader("QUESTION")
    st.write(question.strip())
    st.subheader("ANALYSIS STATUS")
    with st.status("Running analysis...", expanded=True) as status:
        report = agent.analyze(question.strip(), tables, progress=lambda s: status.write(f"▶ {s}"), profiles=profiles)
        for s in STAGES:
            if s not in report.stages:
                status.write(f"— {s} (not reached)")
        status.update(label=f"Done — {report.status.value}", state="complete")
    st.session_state["report"] = report

report = st.session_state.get("report")
if report:
    ev, ver = report.evidence, report.verification

    st.subheader("FINAL ANSWER")
    if report.status == Status.VERIFIED and report.structured_result is not None:
        st.write("**" + report.answer + "**")      # built by the application from the verified structured result
        if report.explanation:
            st.caption("Explanation (wording by the AI model, checked against the verified result): " + report.explanation)
    elif report.status == Status.CANNOT_DETERMINE:
        st.write(report.answer)
    elif report.status == Status.AI_SERVICE_UNAVAILABLE:
        st.write("The AI service is temporarily unavailable, so no analysis was run. Please retry.")
    else:
        st.write("No verified answer is available for this question.")

    st.subheader("VERIFICATION")
    if report.status == Status.VERIFIED:
        st.success("✅ VERIFIED — the code ran, the structured result is consistent, and the answer matches it.")
    elif report.status == Status.CANNOT_DETERMINE:
        st.warning("⚠ CANNOT DETERMINE")
    elif report.status == Status.AI_SERVICE_UNAVAILABLE:
        st.warning("⏳ AI service is temporarily unavailable. Please retry.")
    elif report.status == Status.PLANNING_FAILED:
        st.error("❌ PLANNING FAILED — the AI request was rejected (check API key / configuration).")
    elif report.status == Status.EXECUTION_FAILED:
        st.error("❌ EXECUTION FAILED")
    else:
        st.error("❌ NOT VERIFIED")
    if report.reason:
        st.write("**Reason:** " + report.reason)
    if report.rejected_answer:
        st.caption("Rejected explanation (contradicted the executed result): " + report.rejected_answer)
    if ver and ver.checks:
        st.write("  ".join(f"{'✅' if v else '❌'} {k.replace('_', ' ')}" for k, v in ver.checks.items()))

    st.subheader("DATA SOURCES")
    if ev and ev.files_used:
        for n in ev.tables_used:
            st.write(f"- `{n}` — columns used: {', '.join(ev.columns_used.get(n, [])) or '—'}")
    else:
        st.write("No dataset was used.")

    st.subheader("DATA QUALITY")
    for i in report.issues:
        label = f"{i.table + ': ' if i.table else ''}{i.message}"
        if i.severity == Severity.BLOCKING:
            st.error("🚫 BLOCKING — " + label)
        elif i.severity == Severity.WARNING:
            st.warning("⚠ WARNING — " + label)
        else:
            st.success("SAFE — " + label)
    if not report.issues:
        for b_ in report.blocking_issues:
            st.error("🚫 BLOCKING — " + b_)
    if report.quality_notes:
        with st.expander(f"Dataset-level warnings ({len(report.quality_notes)})"):
            for n in report.quality_notes:
                st.write(n)
    if ev:
        for r_ in ev.data_quality_records:
            lines = [f"**{r_.table}** — original rows: {r_.original_rows:,} · duplicate rows detected: {r_.duplicate_rows_detected:,} · "
                     f"duplicate rows removed: {r_.duplicate_rows_removed:,} · rows used for calculation: {r_.rows_used:,}"]
            lines += [f"{c}: missing values {m['missing']:,} · rows excluded {m['rows_excluded']:,}" for c, m in r_.missing.items()]
            if r_.note:
                lines.append(r_.note)
            st.info("  \n".join(lines))

    if report.code:
        st.subheader("GENERATED CODE")
        st.code(report.code, language="python")

    if report.execution:
        st.subheader("EXECUTION RESULT")
        if report.structured_result:
            st.write("**" + summarize_result(report.structured_result) + "**")
            st.json(report.structured_result.model_dump(exclude_none=True))
        else:
            st.code(report.execution.stdout or report.execution.stderr or "(no output)")

    if ev:
        st.subheader("PROVENANCE / EVIDENCE")
        st.write(f"**Files:** {', '.join(ev.files_used) or '—'}  ·  **Sheets:** {', '.join(ev.sheets_used) or '—'}")
        st.write("**Joins:** " + ("; ".join(ev.joins) or "none"))
        st.write("**Filters:** " + ("; ".join(ev.filters) or "none"))
        st.write("**Transformations:** " + ("; ".join(ev.transformations) or "none"))
        st.caption(f"LLM calls: {report.llm_calls}/3 · Recorded {ev.timestamp} · code sha256 {ev.code_sha256[:16]}… · data fingerprints {ev.data_fingerprints}")
        with st.expander("Full audit record (JSON)"):
            st.download_button("Download audit JSON", report.model_dump_json(indent=2), file_name=f"audit_{report.audit_id}.json")
            st.json(report.model_dump(mode="json"))
