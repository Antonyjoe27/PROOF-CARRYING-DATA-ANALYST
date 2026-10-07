"""Deterministic, structured verification.

Pipeline:  verify_execution()  -> is the *computation* trustworthy?   (no LLM involved)
           verify_answer()     -> does the natural-language answer match the structured result?
           verify()            -> both, in one call.
Status mapping: blocking data problems -> CANNOT_DETERMINE; failed run -> EXECUTION_FAILED;
malformed/inconsistent result or contradicting answer -> NOT_VERIFIED; everything passes -> VERIFIED.
"""
import json
import math
import re

from backend.models.schemas import AnswerClaim, DataIssue, Severity, Status, StructuredResult, VerificationResult
from . import validation as V

ROUNDING_ABS = 0.005     # numbers are equal if they match up to rounding to 2 decimals (or the decimals shown in text)
_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_OP_SYN = {"average": "mean", "avg": "mean", "mean": "mean", "sum": "sum", "total": "sum", "median": "median",
           "count": "count", "max": "max", "maximum": "max", "min": "min", "minimum": "min"}
_OP_WORDS = {"mean": r"\b(average|mean|avg)\b", "sum": r"\b(total|sum)\b", "median": r"\bmedian\b",
             "count": r"\b(count|how many|number of)\b"}
_HIGH = r"\b(highest|most|best|top|largest|biggest|maximum|greatest)\b"
_LOW = r"\b(lowest|least|worst|smallest|minimum|fewest)\b"
_UNIT_SYN = {"₹": "INR", "rs": "INR", "inr": "INR", "rupee": "INR", "rupees": "INR", "$": "USD", "usd": "USD",
             "dollar": "USD", "dollars": "USD", "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR"}


def norm_unit(u: str) -> str:
    u = (u or "").strip().lower()
    return _UNIT_SYN.get(u, u.upper() if u in ("%",) else u)


def norm_op(o: str | None) -> str:
    return _OP_SYN.get((o or "").strip().lower(), (o or "").strip().lower())


def _close(a: float, b: float, decimals: int | None = None) -> bool:
    tol = ROUNDING_ABS if decimals is None else 0.5 * 10 ** -decimals + 1e-9
    return abs(a - b) <= max(tol, 1e-9 * abs(b))


def _numbers(text: str) -> list[tuple[float, int]]:
    out = []
    for tok in _NUM.findall(text):
        t = tok.replace(",", "")
        try:
            out.append((float(t), len(t.split(".")[1]) if "." in t else 0))
        except ValueError:
            pass
    return out


def format_value(value, unit: str = "") -> str:
    if value is None:
        return "n/a"
    s = f"{value:,.2f}".rstrip("0").rstrip(".")
    u = norm_unit(unit)
    return f"₹{s}" if u == "INR" else f"${s}" if u == "USD" else f"€{s}" if u == "EUR" else f"{s} {unit}".strip()


def summarize_result(r: StructuredResult) -> str:
    if r.result_type == "ranking":
        return f"{r.selected_entity} → {format_value(r.value, r.unit)} ({r.direction} {r.metric})"
    if r.result_type == "aggregate":
        return f"{r.operation} of {r.metric} = {format_value(r.value, r.unit)}"
    return "; ".join(f"{k} → {format_value(v, r.unit)}" for k, v in (r.values or {}).items()) + f" ({r.metric})"


# ---------------------------------------------------------------- structured result
def parse_structured_result(stdout: str) -> tuple[StructuredResult | None, str]:
    """Take the last stdout line that is a JSON object with a `result_type`."""
    for line in reversed([ln for ln in stdout.strip().splitlines() if ln.strip()]):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict) and "result_type" in obj:
            try:
                return StructuredResult.model_validate(obj), ""
            except Exception as e:
                return None, f"Structured result failed validation: {str(e).splitlines()[0]}"
    return None, "No structured JSON result (an object with 'result_type') was printed by the code."


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def check_consistency(r: StructuredResult) -> tuple[list[str], list[str]]:
    """Returns (malformed_problems, insufficient_data_problems)."""
    bad, insufficient = [], []
    if r.rows_used is not None and r.rows_used <= 0:
        insufficient.append("The calculation used 0 rows (no matching data).")
    if r.result_type == "ranking":
        if not r.selected_entity or r.direction is None:
            bad.append("ranking result needs 'selected_entity' and 'direction'")
        if not _finite(r.value):
            insufficient.append("ranking produced no finite value")
        if r.values:
            if any(not _finite(v) for v in r.values.values()):
                insufficient.append("ranking 'values' contain missing/non-finite numbers")
            elif r.selected_entity not in r.values:
                bad.append("selected_entity is not among the reported 'values'")
            else:
                best = (max if r.direction == "highest" else min)(r.values.values())
                if not _close(r.values[r.selected_entity], best):
                    bad.append(f"selected_entity is not the {r.direction} of the reported values")
                if _finite(r.value) and not _close(r.value, r.values[r.selected_entity]):
                    bad.append("'value' does not equal the selected entity's reported value")
    elif r.result_type == "aggregate":
        if not r.operation:
            bad.append("aggregate result needs 'operation'")
        if not _finite(r.value):
            insufficient.append("aggregate produced no finite value (insufficient data)")
    else:  # comparison
        if not r.entities or not r.values:
            bad.append("comparison result needs 'entities' and 'values'")
        elif set(r.entities) != set(r.values):
            bad.append("comparison 'entities' and 'values' keys differ")
        elif any(not _finite(v) for v in r.values.values()):
            insufficient.append("comparison values contain missing/non-finite numbers")
    return bad, insufficient


def check_question_intent(question: str, r: StructuredResult) -> list[str]:
    q = question.lower()
    out = []
    if r.result_type == "ranking" and r.direction:
        hi, lo = bool(re.search(_HIGH, q)), bool(re.search(_LOW, q))
        if hi != lo and (r.direction == "highest") != hi:
            out.append(f"Question asks for the {'highest' if hi else 'lowest'} but the result is the {r.direction}.")
    if r.result_type == "aggregate":
        asked = {op for op, pat in _OP_WORDS.items() if re.search(pat, q)}
        if len(asked) == 1 and norm_op(r.operation) not in asked:
            out.append(f"Question asks for the {next(iter(asked))} but the result operation is '{r.operation}'.")
    return out


# ---------------------------------------------------------------- answer vs result
def verify_answer(claim: AnswerClaim, r: StructuredResult, question: str) -> tuple[dict[str, bool], list[str]]:
    checks: dict[str, bool] = {}
    problems: list[str] = []
    text = claim.answer
    low = text.lower()

    def fail(key, msg):
        checks[key] = False
        problems.append(msg)

    # entity
    checks["answer_entity_matches"] = True
    if r.result_type == "ranking":
        if claim.claimed_entity and claim.claimed_entity.strip().lower() != (r.selected_entity or "").strip().lower():
            fail("answer_entity_matches", f"Answer claims '{claim.claimed_entity}' but the executed result selected '{r.selected_entity}'.")
        elif (r.selected_entity or "").lower() not in low:
            fail("answer_entity_matches", f"Answer does not state the executed result's entity '{r.selected_entity}'.")
    elif r.result_type == "comparison":
        miss = [e for e in (r.entities or []) if e.lower() not in low]
        if miss:
            fail("answer_entity_matches", f"Answer omits compared entities: {miss}")

    # value
    checks["answer_value_matches"] = True
    targets = [r.value] if r.result_type != "comparison" else list((r.values or {}).values())
    text_nums = _numbers(text)
    if claim.claimed_value is not None and r.result_type != "comparison" and _finite(r.value) \
            and not _close(claim.claimed_value, r.value):
        fail("answer_value_matches", f"Answer claims value {claim.claimed_value:g} but the executed result is {r.value:g}.")
    pct = "%" in text
    for t in targets:
        if _finite(t) and not any(_close(n, t, d) or (pct and _close(n, t * 100, d)) for n, d in text_nums):
            fail("answer_value_matches", f"Executed value {t:g} is not stated in the answer.")
            break
    allowed = [x for x in targets if _finite(x)] + [n for n, _ in _numbers(question)] \
        + [n for e in (list(r.values or {}) + [r.selected_entity or ""] + (r.entities or [])) for n, _ in _numbers(e)]
    if r.values:
        allowed += list(r.values.values())
    if r.rows_used:
        allowed.append(r.rows_used)
    for n, d in text_nums:
        if not any(_close(n, a, d) or (pct and _close(n, a * 100, d)) for a in allowed):
            fail("answer_value_matches", f"Answer states number {n:g}, which is not in the executed result.")
            break

    # unit
    checks["answer_unit_matches"] = True
    ru = norm_unit(r.unit)
    if claim.claimed_unit and norm_unit(claim.claimed_unit) != ru:
        fail("answer_unit_matches", f"Answer unit '{claim.claimed_unit}' differs from result unit '{r.unit or 'none'}'.")
    else:
        found = set()
        if "₹" in text or re.search(r"\b(inr|rs\.?|rupees?)\b", low): found.add("INR")
        if "$" in text or re.search(r"\b(usd|dollars?)\b", low): found.add("USD")
        if "€" in text or re.search(r"\b(eur|euros?)\b", low): found.add("EUR")
        if found and found != {ru}:
            fail("answer_unit_matches", f"Answer uses currency {sorted(found)} but the executed result unit is '{r.unit or 'none'}'.")

    # operation / direction
    checks["answer_operation_matches"] = True
    if r.result_type == "aggregate":
        op = norm_op(r.operation)
        if claim.claimed_operation and norm_op(claim.claimed_operation) != op:
            fail("answer_operation_matches", f"Answer operation '{claim.claimed_operation}' differs from executed '{r.operation}'.")
        else:
            said = {o for o, pat in _OP_WORDS.items() if re.search(pat, low)}
            if said and op not in said:
                fail("answer_operation_matches", f"Answer describes {sorted(said)} but the executed operation is '{r.operation}'.")
    if r.result_type == "ranking" and r.direction:
        opposite = _LOW if r.direction == "highest" else _HIGH
        same = _HIGH if r.direction == "highest" else _LOW
        if re.search(opposite, low) and not re.search(same, low):
            fail("answer_operation_matches", f"Answer implies the opposite of '{r.direction}'.")

    checks["answer_consistent_with_result"] = all(checks.values())
    return checks, problems


# ---------------------------------------------------------------- execution verification
def _early(status, checks, reasons, issues=None, **kw):
    issues = issues or []
    return VerificationResult(
        status=status, checks=checks, reasons=reasons, issues=issues,
        blocking_issues=[i.message for i in issues if i.severity == Severity.BLOCKING],
        warnings=[i.message for i in issues if i.severity == Severity.WARNING], **kw)


def verify_execution(*, question, plan, execution, tables, profiles, code) -> VerificationResult:
    checks: dict[str, bool] = {}
    issues: list[DataIssue] = []

    def add(sev, kind, msg, table=None, column=None):
        issues.append(DataIssue(severity=sev, kind=kind, message=msg, table=table, column=column))

    B, W = Severity.BLOCKING, Severity.WARNING

    checks["question_answerable"] = plan is None or plan.answerable
    if not checks["question_answerable"]:
        msg = plan.reason or "The question cannot be answered from the provided data."
        return _early(Status.CANNOT_DETERMINE, checks, [msg], [DataIssue(severity=B, kind="unanswerable", message=msg)])

    checks["execution_succeeded"] = bool(execution and execution.success)
    if not checks["execution_succeeded"]:
        return _early(Status.EXECUTION_FAILED, checks,
                      ["Code execution failed: " + (execution.stderr[-300:] if execution else "not executed")])

    # ---- data-quality / answerability issues, classified SAFE / WARNING / BLOCKING
    missing_src = [s for s in (plan.required_sources if plan else []) if s not in tables]
    checks["required_sources_available"] = not missing_src
    if missing_src:
        add(B, "missing_file", f"Required data not provided: {', '.join(missing_src)}")

    miss_cols = V.missing_columns(plan, tables) if plan else []
    checks["required_columns_exist"] = not miss_cols
    if miss_cols:
        add(B, "missing_column", f"Required column(s) not found in the provided data: {', '.join(miss_cols)}")

    used, cols = V.code_usage(code, tables)
    checks["code_uses_provided_data"] = bool(used)

    amb = [(n, c) for n in used for c in cols[n] for cp in profiles[n].columns if cp.name == c and cp.ambiguous_date]
    checks["dates_unambiguous"] = not amb
    for n, c in amb:
        add(B, "ambiguous_date", "The question cannot be answered reliably because the dataset contains an ambiguous date format "
                                 f"(dd/mm vs mm/dd): {n}.{c}.", n, c)

    conflicts = V.detect_conflicts(tables, used)
    checks["sources_consistent"] = not conflicts
    for c in conflicts:
        add(B, "conflicting_sources", "Conflicting sources: " + c)

    joins = V.impossible_joins(tables, used) if "merge" in code or ".join(" in code else []
    checks["joins_valid"] = not joins
    for j in joins:
        add(B, "impossible_join", j)

    units = V.unit_mismatches(used, cols, profiles)
    checks["units_consistent"] = not units
    for u in units:
        add(B, "unit_mismatch", u)

    dup_tables = [n for n in used if profiles[n].duplicate_rows]
    checks["duplicates_handled"] = not dup_tables or V.handles_duplicates(code)
    for n in dup_tables:
        if V.handles_duplicates(code):
            add(W, "duplicates_handled", f"{profiles[n].duplicate_rows} exact duplicate rows removed by drop_duplicates() before calculation", n)
        else:
            add(B, "duplicates", f"Unresolved duplicate rows in: {n} (code does not de-duplicate).", n)

    miss = [(n, c, cp.missing) for n in used for c in cols[n] for cp in profiles[n].columns if cp.name == c and cp.missing]
    checks["missing_values_handled"] = not miss or V.handles_missing(code)
    for n, c, k in miss:
        if V.handles_missing(code):
            add(W, "missing_handled", f"{k} missing values handled explicitly in code (dropna/fillna)", n, c)
        else:
            add(B, "missing_values", f"Unresolved missing values in: {n}.{c} ({k}) (code does not handle them).", n, c)

    blocking = [i for i in issues if i.severity == B]
    if blocking:
        return _early(Status.CANNOT_DETERMINE, checks, [i.message for i in blocking], issues)
    if not used:
        return _early(Status.NOT_VERIFIED, checks, ["Generated code does not reference any uploaded dataset."], issues)
    for n in used:
        if not any(i.table == n for i in issues):
            add(Severity.SAFE, "clean", "No duplicate, missing-value or ambiguity issues detected in the columns used", n)

    # ---- structured result
    result, err = parse_structured_result(execution.stdout)
    checks["structured_result_present"] = result is not None
    if result is None:
        return _early(Status.NOT_VERIFIED, checks, [err], issues)
    bad, insufficient = check_consistency(result)
    checks["result_internally_consistent"] = not bad
    if bad:
        return _early(Status.NOT_VERIFIED, checks, ["Inconsistent structured result: " + "; ".join(bad)], issues,
                      structured_result=result)
    checks["sufficient_data"] = not insufficient
    if insufficient:
        for m in insufficient:
            add(B, "insufficient_data", m)
        return _early(Status.CANNOT_DETERMINE, checks, insufficient, issues, structured_result=result)
    intent = check_question_intent(question, result)
    checks["result_matches_question_intent"] = not intent
    if intent:
        return _early(Status.NOT_VERIFIED, checks, intent, issues, structured_result=result)

    return _early(Status.VERIFIED, checks, [], issues, structured_result=result)


def verify(*, question, plan, execution, answer, tables, profiles, code) -> VerificationResult:
    """Execution verification, then (if `answer` is given) answer-vs-result verification."""
    ver = verify_execution(question=question, plan=plan, execution=execution, tables=tables, profiles=profiles, code=code)
    if ver.status != Status.VERIFIED or answer is None:
        return ver
    claim = answer if isinstance(answer, AnswerClaim) else AnswerClaim(answer=str(answer))
    checks, problems = verify_answer(claim, ver.structured_result, question)
    ver.checks.update(checks)
    if problems:
        ver.status, ver.reasons = Status.NOT_VERIFIED, problems
    return ver
