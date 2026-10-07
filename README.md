# Proof-Carrying Data Analyst
**HACKNEX 2026 · HNX26PSI08** — *An AI data analyst that proves its answers.*

## Problem
LLM analysts return confident numbers with no evidence. This system answers questions over messy, multi-table data and returns the answer **plus executable proof**: the code that ran, its real output, the sources/columns used, and an honest verification status. If the data cannot support an answer, it says so.

## Architecture
```
Question -> Retrieval (files/sheets/columns) -> LLM CALL 1: structured plan + code
 -> Static sandbox validation -> Subprocess execution -> STRUCTURED JSON result
 -> Deterministic verifier -> (only if verified) LLM explains -> explanation re-verified -> Evidence + audit log
```
LLM plans, writes code and explains. **All numbers come from executed Python**; LLM never computes and cannot overwrite verified values.

| Module | Responsibility |
|---|---|
| `agent/` | Orchestration, prompts, planning, explanation |
| `ingestion/` | CSV/XLSX loading; PDF placeholder reports "PDF support is not yet enabled" |
| `analysis/` | Profiling, quality warnings, join keys, schema text |
| `retrieval/` | Question -> relevant file/sheet/columns (names, types, synonyms, value matching; no embeddings) |
| `code_generation/` | Prompt building for plan+code (call 1) and repair (call 2) |
| `execution/` | AST validation + restricted subprocess |
| `verification/` | Structured verifier + deterministic data-quality checks |
| `provenance/` | Evidence derived from the code that actually ran, audit logs |
| `llm/`, `models/`, `frontend/` | LLM client, Pydantic schemas, Streamlit UI |

## LLM usage (hard cap: 3 calls per question)
1. **Plan + code in one structured response** (`PlanAndCode`, Pydantic-validated; malformed -> retried once, then a controlled failure).
2. **One repair call only if needed** (execution error, malformed result, fixable duplicate/missing-value handling, sandbox rejection).
3. **Explanation of an already verified result**, re-verified against the structured result.
Questions about years absent from the data cost 0 calls. Profiling, retrieval, validation, verification and provenance never call LLM. Model name comes from `OPENROUTER_MODEL`.

## Caching
Uploaded files are parsed once per file *content hash* (`st.cache_data`); dataset profiles are computed once per dataset version (content fingerprint) and reused for later questions. Final answers are never cached by question text.

## Final answer rule
The final answer is **built by the application** from the verified structured result (entity, value, unit, operation/direction, comparison values are injected by code). LLM supplies wording only (`explanation`), which is re-verified against the result and shown separately. If LLM's wording contradicts the result, the status is `NOT_VERIFIED` and no answer is shown. `AnalysisReport` fails closed: it cannot be `VERIFIED` without a structured result, and non-verified statuses cannot carry an answer.

## Structured results
Generated code must end with one `print(json.dumps(result))` using one of: `ranking` (`selected_entity`, `value`, `direction`, `values` for all entities), `aggregate` (`operation`, `value`, `rows_used`) or `comparison` (`entities`, `values`); optional `unit`.

## Verification
Statuses: `VERIFIED` · `NOT_VERIFIED` · `CANNOT_DETERMINE` · `EXECUTION_FAILED`.

1. `verify_execution` (no LLM): run succeeded; required sources/columns exist; dates unambiguous; sources agree; joins non-empty; units consistent; duplicates/missing values handled explicitly in code; structured result present, internally consistent (e.g. selected entity really is the max of the reported values) and matching the question (highest vs lowest, average vs total); enough data. Blocking data problems -> `CANNOT_DETERMINE`; malformed or inconsistent result -> `NOT_VERIFIED`.
2. Only a verified computation is explained by LLM, which also returns the claims it makes (entity, value, unit, operation).
3. `verify_answer` checks those claims and the text against the structured result: entity, value (equal up to rounding to the displayed decimals), unit/currency, operation, direction, and that no number outside the result appears. A contradicting explanation is retried once, then the status is `NOT_VERIFIED`.

## Data quality
Every issue is classified **SAFE / WARNING / BLOCKING** (BLOCKING never yields VERIFIED -> `CANNOT_DETERMINE`). Duplicates: exact duplicates must be dropped in code (`drop_duplicates()`, recorded in provenance with the count); missing values must be excluded/handled explicitly; ambiguous `dd/mm` dates, conflicting sources, impossible joins, currency mismatches, missing columns/files and years absent from the data are blocking. Source data is never altered.

## Execution safety (controlled hackathon environment, NOT a production sandbox)
Allowed imports: pandas, numpy, math, json, datetime, re, statistics, decimal, collections (DuckDB removed). Static AST validation blocks file/network/OS/subprocess/reflection access; the code then runs in an isolated subprocess (`-I`, temp cwd, empty environment so no API keys, CPU and file-size limits, timeout) with restricted builtins (no `open`/`eval`/`exec`), a whitelisting `__import__` and disabled sockets.

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env        # add OPENROUTER_API_KEY (never commit .env)
python data/generate_samples.py
streamlit run frontend/streamlit_app.py   # or: python run.py
python -m backend.main "Which product has the highest profit?" data/sample/sales.csv data/sample/costs.csv   # CLI
pytest
```
Env vars: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `anthropic/claude-sonnet-4.6`), optional `OPENROUTER_FALLBACK_MODELS` (comma list, used only after a final 503) and `OPENROUTER_MAX_RETRIES` (SDK retries, default 2). Base URL: `https://openrouter.ai/api/v1`.

## Example questions
Which product generated the highest profit and what was the profit? · Which region generated the highest revenue? · Average revenue in Q3? · Largest profit margin? · Which category performed best? · What was the profit in 2035? (-> CANNOT_DETERMINE)

## Screenshots
_placeholder_

## MVP vs stretch
**MVP (built, CSV/XLSX only; PDF is not supported yet):** CSV/XLSX ingestion, profiling, LLM planning + codegen, sandboxed execution with one repair retry, verifier, provenance + audit logs, Streamlit UI, offline tests (FakeLLM).
**Stretch:** PDF extraction, embeddings/vector retrieval, voice, local LLM fallback, signed/Merkle proofs, Next.js UI.

## Limitations
The sandbox is layered but not a hardened jail (no container/seccomp); a determined attacker may find gaps. Year guard treats any 19xx/20xx token in the question as a year. The verifier proves the answer matches the executed result and that data-quality rules hold; it cannot prove the generated code's logic is the right interpretation of the question. Conflict detection compares same-named key/numeric columns only.

## External APIs / models / libraries
OpenRouter API (OpenAI-compatible SDK via OpenRouter; model configurable). pandas, numpy, OpenPyXL, Pydantic, python-dotenv, Streamlit, pytest.

## Dataset sources
Synthetic, generated by `data/generate_samples.py` (deterministic; Laptop Pro profit = ₹12,40,000). Edge cases in `data/edge_cases/`.
