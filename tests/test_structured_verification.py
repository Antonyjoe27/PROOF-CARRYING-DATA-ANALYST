import json
import pandas as pd
import pytest
from backend.analysis.data_profiler import profile_table
from backend.ingestion import LoadedTable
from backend.models.schemas import AnalysisPlan, AnswerClaim, ExecutionResult, Status
from backend.verification.verifier import parse_structured_result, verify, verify_answer

RANK = {"result_type": "ranking", "metric": "profit", "selected_entity": "Laptop Pro", "value": 1240000.0, "unit": "INR",
        "direction": "highest", "values": {"Laptop Pro": 1240000.0, "Phone X": 800000.0, "Tablet Z": 180000.0}}
CODE = "print(sales_df.shape, costs_df.shape)"


def ex(obj=None, raw=None, ok=True):
    return ExecutionResult(success=ok, stdout=raw if raw is not None else json.dumps(obj) + "\n", returncode=0 if ok else 1)


def plan(**k):
    return AnalysisPlan(**{**dict(answerable=True, reason="", required_sources=["sales.csv"], required_columns=[], operations=[]), **k})


def run(tables, execution, answer=None, q="Which product has the highest profit?", p=None, code=CODE, tbl=None):
    t = tbl or tables
    return verify(question=q, plan=p or plan(), execution=execution, answer=answer, tables=t,
                  profiles={n: profile_table(x) for n, x in t.items()}, code=code)


# ---- 1-5: correct answers verify (ranking highest / lowest, aggregate, group-by, comparison) ----
def test_highest_verified(tables):
    r = run(tables, ex(RANK), AnswerClaim(answer="Laptop Pro had the highest profit: ₹1,240,000.", claimed_entity="Laptop Pro",
                                          claimed_value=1240000, claimed_unit="INR"))
    assert r.status == Status.VERIFIED and r.checks["answer_consistent_with_result"]


def test_lowest_verified(tables):
    low = {**RANK, "selected_entity": "Tablet Z", "value": 180000.0, "direction": "lowest"}
    r = run(tables, ex(low), AnswerClaim(answer="Tablet Z had the lowest profit: ₹180,000.", claimed_entity="Tablet Z"),
            q="Which product has the lowest profit?")
    assert r.status == Status.VERIFIED


def test_average_verified(tables):
    agg = {"result_type": "aggregate", "metric": "revenue", "operation": "mean", "value": 842000.5, "unit": "INR", "rows_used": 60}
    r = run(tables, ex(agg), AnswerClaim(answer="The average revenue in Q3 was ₹842,000.50.", claimed_operation="average",
                                         claimed_value=842000.5), q="What was the average revenue in Q3?")
    assert r.status == Status.VERIFIED


def test_group_by_ranking_verified(tables):
    assert run(tables, ex(RANK), "Laptop Pro led on profit at 1,240,000; Phone X had 800,000.").status == Status.VERIFIED


def test_comparison_verified_and_incomplete_answer_rejected(tables):
    cmp = {"result_type": "comparison", "entities": ["North", "South"], "metric": "revenue", "values": {"North": 500000.0, "South": 700000.0}}
    q = "Compare revenue between North and South"
    assert run(tables, ex(cmp), "North made 500,000 and South made 700,000.", q=q).status == Status.VERIFIED
    assert run(tables, ex(cmp), "South made 700,000.", q=q).status == Status.NOT_VERIFIED


# ---- 6-8: the number is in stdout but the CONCLUSION is wrong ----
def test_wrong_entity_despite_number_in_stdout(tables):
    r = run(tables, ex(RANK), AnswerClaim(answer="Phone X had the highest profit: 800,000", claimed_entity="Phone X", claimed_value=800000))
    assert r.status == Status.NOT_VERIFIED and not r.checks["answer_entity_matches"]
    # text-only claims are caught too
    assert run(tables, ex(RANK), "Phone X had the highest profit: 800,000").status == Status.NOT_VERIFIED


def test_right_entity_but_another_entitys_value(tables):
    r = run(tables, ex(RANK), "Laptop Pro had the highest profit: 800,000.")
    assert r.status == Status.NOT_VERIFIED and not r.checks["answer_value_matches"]


def test_wrong_value(tables):
    r = run(tables, ex(RANK), AnswerClaim(answer="Laptop Pro made 1,300,000.", claimed_entity="Laptop Pro", claimed_value=1300000))
    assert r.status == Status.NOT_VERIFIED and not r.checks["answer_value_matches"]


def test_wrong_unit(tables):
    assert not run(tables, ex(RANK), AnswerClaim(answer="Laptop Pro made 1,240,000 USD.", claimed_unit="USD")).checks["answer_unit_matches"]
    assert not run(tables, ex(RANK), "Laptop Pro made $1,240,000 in profit.").checks["answer_unit_matches"]
    no_unit = {**RANK, "unit": ""}
    assert not run(tables, ex(no_unit), "Laptop Pro made ₹1,240,000 in profit.").checks["answer_unit_matches"]


def test_wrong_operation_and_direction(tables):
    agg = {"result_type": "aggregate", "metric": "revenue", "operation": "mean", "value": 100.0}
    assert not run(tables, ex(agg), "The total revenue was 100.", q="average revenue?").checks["answer_operation_matches"]
    assert not run(tables, ex(RANK), "Laptop Pro had the lowest profit at 1,240,000.").checks["answer_operation_matches"]


def test_tolerance_is_explicit_rounding_only(tables):
    ok = run(tables, ex({**RANK, "value": 1234.567, "values": {"Laptop Pro": 1234.567}}), "Laptop Pro made 1,234.57 profit.")
    rounded = run(tables, ex({**RANK, "value": 1234.567, "values": {"Laptop Pro": 1234.567}}), "Laptop Pro made 1,235 profit.")
    assert ok.status == Status.VERIFIED and rounded.status == Status.VERIFIED  # 1,235 is a valid rounding to 0 decimals
    off = run(tables, ex({**RANK, "value": 1234.567, "values": {"Laptop Pro": 1234.567}}), "Laptop Pro made 1,240 profit.")
    assert off.status == Status.NOT_VERIFIED


# ---- 20-21: malformed / inconsistent structured output ----
@pytest.mark.parametrize("raw", ["Laptop Pro 1240000\n", "", "{not json}", '{"foo": 1}', '{"result_type": "ranking"',
                                 '{"result_type": "banana", "value": 1}'])
def test_malformed_structured_output(tables, raw):
    r = run(tables, ex(raw=raw), "Laptop Pro 1240000")
    assert r.status == Status.NOT_VERIFIED and not r.checks["structured_result_present"]
    assert parse_structured_result(raw)[0] is None


@pytest.mark.parametrize("mutate", [
    {"selected_entity": "Phone X", "value": 800000.0},                      # not the max of its own values
    {"value": 5.0},                                                          # value != values[selected]
    {"direction": "lowest"},                                                 # claims lowest but selected is max
    {"selected_entity": "Ghost", "value": 1.0},                              # entity not in values
    {"selected_entity": None},
])
def test_inconsistent_result_rejected(tables, mutate):
    r = run(tables, ex({**RANK, **mutate}), "anything", q="Which product has the best profit?")
    assert r.status == Status.NOT_VERIFIED and not r.checks.get("result_internally_consistent", True)


def test_comparison_inconsistent(tables):
    r = run(tables, ex({"result_type": "comparison", "entities": ["A", "B"], "values": {"A": 1.0, "C": 2.0}}), "x")
    assert r.status == Status.NOT_VERIFIED


def test_result_contradicts_question_intent(tables):
    low = {**RANK, "selected_entity": "Tablet Z", "value": 180000.0, "direction": "lowest"}
    r = run(tables, ex(low), "Tablet Z 180,000", q="Which product has the highest profit?")
    assert r.status == Status.NOT_VERIFIED and not r.checks["result_matches_question_intent"]
    agg = {"result_type": "aggregate", "metric": "revenue", "operation": "sum", "value": 5.0}
    assert run(tables, ex(agg), "5", q="What was the average revenue?").status == Status.NOT_VERIFIED


@pytest.mark.parametrize("obj", [{"result_type": "aggregate", "metric": "revenue", "operation": "mean", "value": None},
                                 {"result_type": "aggregate", "metric": "revenue", "operation": "mean", "value": 1.0, "rows_used": 0}])
def test_insufficient_data_cannot_determine(tables, obj):
    r = run(tables, ex(obj), "x", q="average revenue?")
    assert r.status == Status.CANNOT_DETERMINE and r.blocking_issues


def test_nan_value_is_insufficient(tables):
    r = run(tables, ex(raw='{"result_type":"aggregate","metric":"r","operation":"mean","value":NaN}\n'), "x", q="average revenue?")
    assert r.status == Status.CANNOT_DETERMINE


# ---- blocking data issues ----
def test_missing_column_in_plan(tables):
    r = run(tables, ex(RANK), "x", p=plan(required_columns=["Profit Margin"]))
    assert r.status == Status.CANNOT_DETERMINE and "Profit Margin" in r.blocking_issues[0]
    assert run(tables, ex(RANK), None, p=plan(required_columns=["Revenue", "Profit"], derived_columns=["Profit"])).status == Status.VERIFIED


def test_missing_source_plan(tables):
    assert run(tables, ex(RANK), "x", p=plan(required_sources=["inventory.csv"])).status == Status.CANNOT_DETERMINE


def test_impossible_join():
    a = LoadedTable("a.csv", "a_df", "a.csv", None, pd.DataFrame({"Product": ["x", "y"], "Revenue": [1, 2]}))
    b = LoadedTable("b.csv", "b_df", "b.csv", None, pd.DataFrame({"Product": ["p", "q"], "Cost": [1, 2]}))
    t = {"a.csv": a, "b.csv": b}
    r = run(None, ex(RANK), None, tbl=t, p=plan(required_sources=["a.csv", "b.csv"]), code="m = a_df.merge(b_df, on='Product')")
    assert r.status == Status.CANNOT_DETERMINE and not r.checks["joins_valid"]


def test_unit_mismatch_between_used_columns():
    a = LoadedTable("a.csv", "a_df", "a.csv", None, pd.DataFrame({"Product": ["x"], "Revenue_USD": [1]}))
    b = LoadedTable("b.csv", "b_df", "b.csv", None, pd.DataFrame({"Product": ["x"], "Cost_INR": [1]}))
    t = {"a.csv": a, "b.csv": b}
    r = run(None, ex(RANK), None, tbl=t, p=plan(required_sources=["a.csv", "b.csv"]),
            code='m = a_df.merge(b_df, on="Product"); m["Revenue_USD"] - m["Cost_INR"]')
    assert r.status == Status.CANNOT_DETERMINE and not r.checks["units_consistent"]


def test_verify_answer_direct_api():
    from backend.models.schemas import StructuredResult
    sr = StructuredResult(**RANK)
    checks, problems = verify_answer(AnswerClaim(answer="Laptop Pro: 1,240,000", claimed_entity="Laptop Pro"), sr, "q")
    assert not problems and checks["answer_consistent_with_result"]
