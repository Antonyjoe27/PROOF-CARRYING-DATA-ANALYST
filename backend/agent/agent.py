"""Single orchestrator.  LLM proposes -> Python computes -> verifier proves.

LLM budget per question (hard cap 3):
  call 1  plan + code in ONE structured response
  call 2  only if needed: ONE repair (execution error / malformed result / fixable data-quality issue / malformed response)
  call 3  explanation of an already VERIFIED result (if the repair was not needed; otherwise it is the last call)
All profiling, retrieval, validation, verification and provenance are deterministic Python (no LLM calls).
"""
from pathlib import Path

from pydantic import ValidationError

from backend.analysis.data_profiler import cross_table_warnings, profile_table
from backend.analysis.schema_analyzer import describe_schema
from backend.code_generation.generator import (clean_plan_and_code, clean_repair, plan_and_code_prompt, repair_prompt)
from backend.execution.executor import execute_code
from backend.execution.sandbox import validate_code
from backend.models.schemas import (AnalysisReport, AnswerClaim, CodeResponse, DataIssue, ExecutionResult, PlanAndCode,
                                    Severity, Status)
from backend.provenance.evidence import build_evidence, fingerprint, save_audit
from backend.retrieval.retriever import retrieve
from backend.verification import validation as V
from backend.verification.verifier import verify_answer, verify_execution
from backend.llm.errors import AIServiceUnavailable, LLMRequestError, USER_UNAVAILABLE_MSG
from .planner import explain_prompt, render_answer

OUTPUTS = Path(__file__).resolve().parents[2] / "outputs"
STAGES = ["Understanding question", "Finding data", "Generating code", "Executing code", "Verifying result"]
ABSTAIN = "I cannot determine this from the provided data."
MAX_LLM_CALLS = 3
_DQ_FIXABLE = {"duplicates_handled", "missing_values_handled"}


class LLMFailure(Exception):
    """LLM unavailable, malformed twice, or call budget exhausted -> controlled failure."""


class AIUnavailable(LLMFailure):
    """LLM 503 on every configured model (after fallbacks). Not a data, execution or verification problem."""


class PlanningRejected(LLMFailure):
    """LLM refused the request itself (invalid key / bad request). Fallback models would not help."""


class _BudgetedLLM:
    def __init__(self, llm, limit=MAX_LLM_CALLS):
        self.llm, self.limit, self.calls = llm, limit, 0

    @property
    def remaining(self):
        return self.limit - self.calls

    def ask(self, prompt, schema):
        if self.calls >= self.limit:
            raise LLMFailure(f"LLM call budget ({self.limit}) exhausted")
        self.calls += 1
        try:
            return self.llm.generate_structured(prompt, schema)
        except (ValidationError, ValueError, KeyError, TypeError) as e:       # malformed structured output
            raise _Malformed(str(e).splitlines()[0][:200]) from e
        except AIServiceUnavailable as e:
            raise AIUnavailable(USER_UNAVAILABLE_MSG) from e
        except LLMRequestError as e:
            raise PlanningRejected(str(e)) from e
        except Exception as e:                                                 # API/network problems
            raise LLMFailure(f"LLM request failed: {type(e).__name__}: {str(e)[:200]}") from e


class _Malformed(Exception):
    pass


def _resolve(name: str, tables) -> str | None:
    if name in tables:
        return name
    hits = [n for n, t in tables.items() if t.source_file == name or n.startswith(name + "::")]
    return hits[0] if len(hits) == 1 else None


def _repair_reason(ex, ver) -> str | None:
    """Fixable problems that deserve the single repair call (never a way to force a verdict)."""
    if not ex.success:
        return None if (ex.timed_out or ex.blocked_reasons) else "Runtime error:\n" + ex.stderr[-1500:]
    failed = {k for k, v in ver.checks.items() if not v}
    if ver.status == Status.CANNOT_DETERMINE and failed and failed <= _DQ_FIXABLE:
        return ("Data-quality rule violated: " + "; ".join(ver.reasons) + " Call drop_duplicates() on tables with exact duplicates "
                "and dropna(subset=[columns you use]) for missing values, then recompute.")
    if ver.status == Status.NOT_VERIFIED and failed & {"structured_result_present", "result_internally_consistent",
                                                         "result_matches_question_intent"}:
        return "Structured result problem: " + "; ".join(ver.reasons)
    return None


class DataAnalystAgent:
    def __init__(self, llm, outputs_dir=OUTPUTS, timeout: int = 30):
        self.llm, self.outputs_dir, self.timeout = llm, outputs_dir, timeout
        self._profile_cache: dict = {}      # (table name, content fingerprint) -> DatasetProfile

    def profile(self, tables):
        """Profiles are computed once per dataset VERSION (content fingerprint) and reused for later questions."""
        profiles = {}
        for n, t in tables.items():
            key = (n, fingerprint(t.df), tuple(map(str, t.df.columns)))
            if key not in self._profile_cache:
                self._profile_cache[key] = profile_table(t)
            profiles[n] = self._profile_cache[key]
        return profiles, cross_table_warnings(profiles)

    def _finish(self, report: AnalysisReport) -> AnalysisReport:
        report.audit_id = save_audit(report, self.outputs_dir)
        return report

    def analyze(self, question: str, tables: dict, progress=None, profiles=None) -> AnalysisReport:
        stages: list[str] = []
        llm = _BudgetedLLM(self.llm)
        if hasattr(self.llm, "notify"):
            self.llm.notify = progress      # lets the client tell the user it is trying a fallback model

        def step(s):
            stages.append(s)
            if progress:
                progress(s)

        if profiles is None:
            profiles, cross = self.profile(tables)
        else:
            cross = cross_table_warnings(profiles)
        notes = cross + [f"{n}: {w}" for n, p in profiles.items() for w in p.warnings]

        def report(**kw):
            base = dict(question=question, stages=stages, quality_notes=notes, llm_calls=llm.calls)
            return self._finish(AnalysisReport(**{**base, **kw}))

        def cannot(reason, kind, plan=None):
            return report(status=Status.CANNOT_DETERMINE, reason=reason, plan=plan, answer=ABSTAIN, blocking_issues=[reason],
                          issues=[DataIssue(severity=Severity.BLOCKING, kind=kind, message=reason)])

        def failed(reason, plan=None, code="", execution=None):
            return report(status=Status.EXECUTION_FAILED, reason=reason, plan=plan, code=code, execution=execution)

        # ---- 1. understand: deterministic guards BEFORE any LLM call ----
        step("Understanding question")
        if not tables:
            return cannot("No supported datasets were provided.", "no_data")
        bad_years = V.unsupported_years(question, profiles)
        if bad_years:
            return cannot("No records for " + ", ".join(map(str, bad_years)) + " exist in the supplied data.", "unknown_year")
        shortlist = retrieve(question, tables, profiles)
        retrieval_notes = [f"{r.name}: {'; '.join(r.reasons) or 'shortlisted'}" for r in shortlist]
        relevant = {r.name: r.columns for r in shortlist}
        schema = describe_schema(tables, profiles, only={r.name for r in shortlist}, relevant=relevant)

        # CALL 1: plan + code (one retry only if the structured response is malformed)
        repair_used = False
        prompt = plan_and_code_prompt(question, schema)
        try:
            try:
                pc = llm.ask(prompt, PlanAndCode)
            except _Malformed as e:
                repair_used = True
                pc = llm.ask(prompt + f"\n\nYour previous response was malformed ({e}). Return valid JSON matching the schema.", PlanAndCode)
        except _Malformed as e:
            return failed(f"LLM returned a malformed structured response twice: {e}")
        except AIUnavailable:
            # LLM outage before any code existed: never EXECUTION_FAILED / CANNOT_DETERMINE / NOT_VERIFIED, never an answer.
            return report(status=Status.AI_SERVICE_UNAVAILABLE, reason=USER_UNAVAILABLE_MSG)
        except PlanningRejected as e:
            return report(status=Status.PLANNING_FAILED, reason=str(e))
        except LLMFailure as e:
            return failed(str(e))
        plan = clean_plan_and_code(pc).to_plan()
        if not plan.answerable:
            return cannot(plan.reason or "The question is not answerable from the provided data.", "unanswerable", plan)

        # ---- 2. find data ----
        step("Finding data")
        resolved = []
        for s in plan.required_sources:
            r = _resolve(s, tables)
            if r is None:
                return cannot(f"Required data source '{s}' was not provided.", "missing_file", plan)
            resolved.append(r)
        plan.required_sources = resolved
        missing = V.missing_columns(plan, tables)
        if missing:
            return cannot(f"Required column(s) not found in the provided data: {', '.join(missing)}.", "missing_column", plan)
        schema = describe_schema(tables, profiles, only=set(plan.required_sources), relevant=relevant)

        def repair(code, problem):
            """CALL 2 (at most once per question). Returns new code or None."""
            nonlocal repair_used
            if repair_used or llm.remaining < 1:
                return None
            repair_used = True
            try:
                return clean_repair(llm.ask(repair_prompt(question, plan, schema, code, problem), CodeResponse))
            except (_Malformed, LLMFailure):
                return None

        # ---- 3. generate / validate ----
        step("Generating code")
        code = plan.code
        errors = validate_code(code)
        if errors:
            code2 = repair(code, "Rejected by the static sandbox: " + "; ".join(errors))
            if code2 is not None:
                code, errors = code2, validate_code(code2)
        plan.code = code
        if errors:
            return failed("Generated code was rejected by the sandbox: " + "; ".join(errors), plan, code,
                          ExecutionResult(success=False, stderr="; ".join(errors), blocked_reasons=errors))

        # ---- 4. execute, 5. verify the computation ----
        step("Executing code")
        frames = {t.variable: t.df.copy() for t in tables.values()}
        ex = execute_code(code, frames, self.timeout)
        step("Verifying result")
        ver = verify_execution(question=question, plan=plan, execution=ex, tables=tables, profiles=profiles, code=code)
        reason = _repair_reason(ex, ver)
        if reason:
            code2 = repair(code, reason)
            if code2 is not None and not validate_code(code2):
                code, plan.code = code2, code2
                ex = execute_code(code, frames, self.timeout)
                ver = verify_execution(question=question, plan=plan, execution=ex, tables=tables, profiles=profiles, code=code)

        # ---- 6. CALL 3: only a VERIFIED computation is explained. The FINAL ANSWER is built by the application from the
        # verified structured result; LLM supplies wording only, and that wording is re-verified against the result.
        answer, explanation, rejected = "", "", None
        if ver.status == Status.VERIFIED:
            sr, fb, accepted = ver.structured_result, "", False
            while llm.remaining >= 1:
                try:
                    claim = llm.ask(explain_prompt(question, sr, fb), AnswerClaim)
                except (_Malformed, LLMFailure):
                    break
                checks, problems = verify_answer(claim, sr, question)
                if not problems:
                    explanation, ver.checks, ver.reasons, accepted = claim.answer, {**ver.checks, **checks}, [], True
                    break
                rejected, fb = claim.answer, "; ".join(problems)
                ver.checks, ver.reasons = {**ver.checks, **checks}, problems
            if accepted:
                answer = render_answer(sr)
            elif rejected is None:
                # LLM unavailable: the application-built answer stands alone (no LLM wording)
                answer = render_answer(sr)
                ver.reasons = []
                ver.warnings.append("No LLM explanation (unavailable); answer shown is generated from the verified result only.")
            else:
                ver.status = Status.NOT_VERIFIED     # LLM's wording contradicted the verified result
        elif ver.status == Status.CANNOT_DETERMINE:
            answer = ABSTAIN

        ev = build_evidence(question, plan, code, ex, ver, tables, profiles, retrieval_notes)
        ev.llm_calls = llm.calls
        return report(status=ver.status, answer=answer, explanation=explanation, reason="; ".join(ver.reasons) or None, plan=plan, code=code,
                      execution=ex, verification=ver, evidence=ev, quality_notes=notes + [w for w in ver.warnings if w not in notes],
                      blocking_issues=ver.blocking_issues, rejected_answer=rejected, structured_result=ver.structured_result,
                      issues=ver.issues)
