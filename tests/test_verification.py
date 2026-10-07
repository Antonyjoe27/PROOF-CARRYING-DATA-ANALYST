from backend.models.schemas import AnalysisPlan, ExecutionResult, Status
from backend.analysis.data_profiler import profile_table
from backend.verification.verifier import verify
from backend.verification.validation import unsupported_years, detect_conflicts

import json
_R = {"result_type": "ranking", "metric": "profit", "selected_entity": "Laptop Pro", "value": 1240000.0,
      "unit": "INR", "direction": "highest", "values": {"Laptop Pro": 1240000.0, "Phone X": 800000.0}}
OK = ExecutionResult(success=True, stdout=json.dumps(_R) + "\n", returncode=0)
CODE = "print(sales_df.shape, costs_df.shape)"


def plan(**k):
    d = dict(answerable=True, reason="", required_sources=["sales.csv"], required_columns=[], operations=[])
    return AnalysisPlan(**{**d, **k})


def run(tables, answer, ex=OK, code=CODE, q="Which product has the highest profit?", p=None, tbl=None):
    t = tbl or tables
    profiles = {n: profile_table(x) for n, x in t.items()}
    return verify(question=q, plan=p or plan(), execution=ex, answer=answer, tables=t, profiles=profiles, code=code)


def test_correct_answer_verified(tables):
    assert run(tables, "Laptop Pro made ₹12,40,000 profit.").status == Status.VERIFIED


def test_wrong_number_rejected(tables):
    r = run(tables, "Laptop Pro made ₹9,99,000 profit.")
    assert r.status == Status.NOT_VERIFIED and not r.checks["answer_value_matches"]


def test_wrong_entity_rejected(tables):
    assert run(tables, "Phone X was best.").status == Status.NOT_VERIFIED


def test_execution_failed(tables):
    assert run(tables, "x", ex=ExecutionResult(success=False, stderr="boom")).status == Status.EXECUTION_FAILED


def test_empty_output_not_verified(tables):
    assert run(tables, "Laptop Pro", ex=ExecutionResult(success=True, stdout="\n")).status == Status.NOT_VERIFIED


def test_unanswerable_plan(tables):
    r = run(tables, "", p=plan(answerable=False, reason="No such column"))
    assert r.status == Status.CANNOT_DETERMINE


def test_unknown_year(tables):
    profiles = {n: profile_table(x) for n, x in tables.items()}
    assert unsupported_years("profit in 2035?", profiles) == [2035]
    assert unsupported_years("profit in 2025?", profiles) == []


def test_duplicates_block_verification(edge):
    t = edge("sales_duplicates.csv")
    r = run(None, "Laptop Pro 1240000", tbl=t, p=plan(required_sources=["sales_duplicates.csv"]), code="print(sales_duplicates_df.shape)")
    assert r.status == Status.CANNOT_DETERMINE and not r.checks["duplicates_handled"]


def test_documented_dedup_allows_verification(edge):
    t = edge("sales_duplicates.csv")
    r = run(None, "Laptop Pro 1240000", tbl=t, p=plan(required_sources=["sales_duplicates.csv"]),
            code="d = sales_duplicates_df.drop_duplicates()")
    assert r.status == Status.VERIFIED


def test_missing_values_block_verification(edge):
    t = edge("sales_missing.csv")
    r = run(None, "Laptop Pro 1240000", tbl=t, p=plan(required_sources=["sales_missing.csv"]),
            code='x = sales_missing_df["Revenue"].sum()')
    assert r.status == Status.CANNOT_DETERMINE and not r.checks["missing_values_handled"]


def test_ambiguous_date_cannot_determine(edge):
    t = edge("sales_ambiguous_dates.csv")
    r = run(None, "Laptop Pro 1240000", tbl=t, p=plan(required_sources=["sales_ambiguous_dates.csv"]),
            code='x = sales_ambiguous_dates_df["Date"]')
    assert r.status == Status.CANNOT_DETERMINE and "ambiguous" in r.reasons[0]


def test_conflicting_sources(edge):
    t = edge("report_conflict.xlsx", "sales_summary.xlsx")
    assert detect_conflicts(t, list(t))
    r = run(None, "Laptop Pro 1240000", tbl=t, p=plan(required_sources=["report_conflict.xlsx"]),
            code="a = report_conflict_df; b = sales_summary_df")
    assert r.status == Status.CANNOT_DETERMINE and "Conflicting" in r.reasons[0]
