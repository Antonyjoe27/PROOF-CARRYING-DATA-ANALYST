from __future__ import annotations
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Status(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    CANNOT_DETERMINE = "CANNOT_DETERMINE"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"   # LLM 503 on every configured model: nothing ran, nothing was verified
    PLANNING_FAILED = "PLANNING_FAILED"                 # LLM rejected the planning call (bad key / bad request): nothing ran
    CODE_GENERATION_FAILED = "CODE_GENERATION_FAILED"
    VERIFICATION_FAILED = "NOT_VERIFIED"                # alias of NOT_VERIFIED (existing name kept for backward compatibility)


class Severity(str, Enum):
    SAFE = "SAFE"            # nothing to worry about
    WARNING = "WARNING"      # analysis may proceed, warning must be shown
    BLOCKING = "BLOCKING"    # result cannot be considered reliable -> never VERIFIED


class DataIssue(BaseModel):
    severity: Severity
    kind: str
    message: str
    table: Optional[str] = None
    column: Optional[str] = None


# ---- LLM structured responses (no Optional fields: keeps the LLM response schema simple) ----
class PlanAndCode(BaseModel):
    """CALL 1: the analysis plan and the code, in ONE structured response."""
    answerable: bool
    reason: str
    sources: list[str]
    columns: list[str]                 # columns that already exist in the data
    derived_columns: list[str] = Field(default_factory=list)   # columns the analysis creates (e.g. Profit)
    operation: str
    transformations: list[str]
    code: str

    @model_validator(mode="after")
    def _answerable_needs_code(self):
        if self.answerable and not self.code.strip():
            raise ValueError("answerable=true but no code was returned")
        if self.answerable and not self.sources:
            raise ValueError("answerable=true but no sources were returned")
        return self

    def to_plan(self) -> "AnalysisPlan":
        return AnalysisPlan(answerable=self.answerable, reason=self.reason, required_sources=list(self.sources),
                            required_columns=list(self.columns), derived_columns=list(self.derived_columns),
                            operation=self.operation, operations=list(self.transformations), code=self.code)


class CodeResponse(BaseModel):
    """CALL 2 (repair only): corrected code."""
    code: str


class AnswerClaim(BaseModel):
    """LLM's explanation of an already-verified result, plus the facts it asserts (checked by the verifier)."""
    answer: str
    claimed_entity: str = ""
    claimed_value: Optional[float] = None
    claimed_unit: str = ""
    claimed_operation: str = ""


class StructuredResult(BaseModel):
    """Machine-readable result that generated code must print as one JSON line."""
    model_config = ConfigDict(coerce_numbers_to_str=True)
    result_type: Literal["ranking", "aggregate", "comparison"]
    metric: str = ""
    value: Optional[float] = None
    unit: str = ""
    selected_entity: Optional[str] = None
    direction: Optional[Literal["highest", "lowest"]] = None
    operation: Optional[str] = None
    entities: Optional[list[str]] = None
    values: Optional[dict[str, float]] = None
    rows_used: Optional[int] = None


class AnalysisPlan(BaseModel):
    answerable: bool
    reason: str = ""
    required_sources: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)
    derived_columns: list[str] = Field(default_factory=list)
    operation: str = ""
    operations: list[str] = Field(default_factory=list)
    code: str = ""


# ---- profiling ----
class ColumnProfile(BaseModel):
    name: str
    dtype: str
    missing: int = 0
    unique: int = 0
    likely_numeric: bool = False
    likely_date: bool = False
    ambiguous_date: bool = False
    years: list[int] = Field(default_factory=list)
    unit_hints: list[str] = Field(default_factory=list)


class DatasetProfile(BaseModel):
    name: str
    variable: str
    source_file: str
    sheet: Optional[str] = None
    rows: int
    columns: list[ColumnProfile]
    duplicate_rows: int = 0
    warnings: list[str] = Field(default_factory=list)


# ---- execution / verification / provenance ----
class ExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: Optional[int] = None
    timed_out: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: Status
    checks: dict[str, bool] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)   # data problems that make a result unreliable
    warnings: list[str] = Field(default_factory=list)          # attention needed, analysis still valid
    structured_result: Optional[StructuredResult] = None
    issues: list[DataIssue] = Field(default_factory=list)


class DataQualityRecord(BaseModel):
    """What the application found and what the executed code did to one table (computed by Python, never by LLM)."""
    table: str
    original_rows: int
    duplicate_rows_detected: int = 0
    duplicate_rows_removed: int = 0
    missing: dict[str, dict[str, int]] = Field(default_factory=dict)   # column -> {"missing": n, "rows_excluded": m}
    rows_used: int = 0
    note: str = ""


class Evidence(BaseModel):
    question: str
    timestamp: str
    files_used: list[str] = Field(default_factory=list)
    tables_used: list[str] = Field(default_factory=list)
    sheets_used: list[str] = Field(default_factory=list)
    columns_used: dict[str, list[str]] = Field(default_factory=dict)
    retrieval: list[str] = Field(default_factory=list)            # why each table was shortlisted
    planned_operations: list[str] = Field(default_factory=list)   # what the model INTENDED (not verified)
    filters: list[str] = Field(default_factory=list)              # extracted from the executed code
    joins: list[str] = Field(default_factory=list)                # extracted from the executed code
    transformations: list[str] = Field(default_factory=list)      # extracted from the executed code
    data_quality_warnings: list[str] = Field(default_factory=list)
    data_quality_actions: list[str] = Field(default_factory=list) # cleaning applied by code, documented
    data_quality_records: list[DataQualityRecord] = Field(default_factory=list)
    structured_result: Optional[StructuredResult] = None
    result_summary: str = ""
    llm_calls: int = 0
    code: str = ""
    code_sha256: str = ""
    execution_status: str = ""
    execution_output: str = ""
    verification_status: str = ""
    data_fingerprints: dict[str, str] = Field(default_factory=dict)


class AnalysisReport(BaseModel):
    question: str
    status: Status
    answer: str = ""
    reason: Optional[str] = None
    explanation: str = ""   # LLM's wording only; the verified fields live in `answer` / `structured_result`
    plan: Optional[AnalysisPlan] = None
    code: str = ""
    execution: Optional[ExecutionResult] = None
    verification: Optional[VerificationResult] = None
    evidence: Optional[Evidence] = None
    quality_notes: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    rejected_answer: Optional[str] = None
    issues: list[DataIssue] = Field(default_factory=list)
    llm_calls: int = 0
    structured_result: Optional[StructuredResult] = None
    stages: list[str] = Field(default_factory=list)
    audit_id: Optional[str] = None

    @model_validator(mode="after")
    def _fail_closed(self):
        """Invariant: a VERIFIED report must carry a verified structured result and an application-built answer;
        any other status can never carry a confident answer."""
        abstain = "I cannot determine this from the provided data."
        if self.status == Status.VERIFIED and (self.structured_result is None or not self.answer.strip()):
            self.status = Status.NOT_VERIFIED
            self.reason = (self.reason or "") + " Internal check: VERIFIED requires a structured result and answer."
        if self.status != Status.VERIFIED:
            if self.status != Status.CANNOT_DETERMINE or self.answer not in ("", abstain):
                self.answer = ""
            self.explanation = ""
        return self
