"""Call budget, malformed/failed LLM responses, profile caching, issue severity, UI claims."""
import pandas as pd
import pytest
from pydantic import ValidationError
from backend.agent import agent as agent_mod
from backend.agent.planner import render_answer
from backend.ingestion import content_hash, load_bytes
from backend.models.schemas import AnswerClaim, PlanAndCode, Severity, Status, StructuredResult
from backend.verification.verifier import verify_answer
from conftest import FakeLLM, GOOD_CLAIM, PROFIT_CODE, SAMPLE

Q = "Which product generated the highest profit?"


# ---- LLM call budget: ONE call for plan+code, +1 explanation; repair only when needed; never more than 3 ----
def test_happy_path_uses_two_calls(tables, make_agent):
    llm = FakeLLM()
    r = make_agent(llm).analyze(Q, tables)
    assert r.status == Status.VERIFIED and llm.calls == ["PlanAndCode", "AnswerClaim"] and r.llm_calls == 2 == r.evidence.llm_calls


def test_unanswerable_year_uses_zero_calls(tables, make_agent):
    llm = FakeLLM()
    assert make_agent(llm).analyze("What was the revenue in 2035?", tables).llm_calls == 0 and llm.calls == []


def test_repair_path_uses_three_calls(tables, make_agent):
    llm = FakeLLM(codes=["print(nope_df)", PROFIT_CODE])
    r = make_agent(llm).analyze(Q, tables)
    assert r.status == Status.VERIFIED and llm.calls == ["PlanAndCode", "CodeResponse", "AnswerClaim"]


def test_second_failure_is_execution_failed_and_bounded(tables, make_agent):
    llm = FakeLLM(codes=["print(1/0)", "print(2/0)"])
    r = make_agent(llm).analyze(Q, tables)
    assert r.status == Status.EXECUTION_FAILED and llm.calls == ["PlanAndCode", "CodeResponse"]


def test_never_more_than_three_calls_even_under_attack(tables, make_agent):
    llm = FakeLLM(codes=["print(1/0)", PROFIT_CODE], answer=AnswerClaim(answer="Phone X won.", claimed_entity="Phone X"))
    r = make_agent(llm).analyze(Q, tables)
    assert len(llm.calls) <= 3 and r.status == Status.NOT_VERIFIED       # explanation rejected, no budget to retry


def test_wrong_explanation_gets_retry_only_if_budget_left(tables, make_agent):
    llm = FakeLLM(answer=AnswerClaim(answer="Phone X won.", claimed_entity="Phone X"))
    r = make_agent(llm).analyze(Q, tables)
    assert r.status == Status.NOT_VERIFIED and llm.calls == ["PlanAndCode", "AnswerClaim", "AnswerClaim"]


# ---- malformed / failing LLM ----
def test_plan_and_code_schema_rejects_incomplete_answerable_response():
    with pytest.raises(ValidationError):
        PlanAndCode(answerable=True, reason="", sources=["a.csv"], columns=[], operation="x", transformations=[], code="  ")
    with pytest.raises(ValidationError):
        PlanAndCode(answerable=True, reason="", sources=[], columns=[], operation="x", transformations=[], code="print(1)")
    assert PlanAndCode(answerable=False, reason="no data", sources=[], columns=[], operation="", transformations=[], code="")


def test_malformed_response_retried_once_then_controlled_failure(tables, make_agent):
    llm = FakeLLM(fail_with=ValueError("not json"))
    r = make_agent(llm).analyze(Q, tables)
    assert r.status == Status.EXECUTION_FAILED and "malformed" in r.reason and llm.calls == ["PlanAndCode", "PlanAndCode"]


def test_malformed_then_valid_recovers(tables, make_agent):
    class Once(FakeLLM):
        n = 0
        def generate_structured(self, prompt, schema):
            Once.n += 1
            if Once.n == 1:
                self.calls.append(schema.__name__)
                raise ValueError("bad json")
            return super().generate_structured(prompt, schema)
    r = make_agent(Once()).analyze(Q, tables)
    assert r.status == Status.VERIFIED and r.llm_calls == 3


def test_api_failure_is_controlled_not_a_crash(tables, make_agent):
    r = make_agent(FakeLLM(fail_with=ConnectionError("network down"))).analyze(Q, tables)
    assert r.status == Status.EXECUTION_FAILED and "LLM request failed" in r.reason


def test_explanation_unavailable_falls_back_to_deterministic_answer(tables, make_agent):
    class NoExplain(FakeLLM):
        def generate_structured(self, prompt, schema):
            if schema is AnswerClaim:
                self.calls.append("AnswerClaim")
                raise ConnectionError("down")
            return super().generate_structured(prompt, schema)
    r = make_agent(NoExplain()).analyze(Q, tables)
    assert r.status == Status.VERIFIED and r.answer.startswith("Laptop Pro had the highest profit: ₹1,240,000")
    assert any("generated from the verified result only" in w for w in r.verification.warnings)


@pytest.mark.parametrize("sr", [
    dict(result_type="ranking", metric="profit", selected_entity="Laptop Pro", value=1240000.0, unit="INR", direction="highest"),
    dict(result_type="aggregate", metric="revenue", operation="mean", value=842000.5, unit="INR"),
    dict(result_type="comparison", metric="revenue", entities=["N", "S"], values={"N": 1.0, "S": 2.0}),
])
def test_deterministic_answer_always_passes_the_verifier(sr):
    r = StructuredResult(**sr)
    assert not verify_answer(AnswerClaim(answer=render_answer(r)), r, "q")[1]


def test_sum_and_grouping_and_filter_verified(tables, make_agent):
    code = ('d = sales_df[sales_df["Region"] == "North"]\n'
            'print(json.dumps({"result_type":"aggregate","metric":"revenue","operation":"sum","value":float(d["Revenue"].sum()),"rows_used":int(len(d))}))')
    total = pd.read_csv(SAMPLE / "sales.csv").query("Region == 'North'").Revenue.sum()
    r = make_agent(FakeLLM(sources=("sales.csv",), code=code, answer=f"The total revenue for North was {int(total):,}.")
                   ).analyze("What was the total revenue in the North region?", tables)
    assert r.status == Status.VERIFIED and r.evidence.filters


# ---- profile once, reuse; content-based invalidation ----
def test_profiles_computed_once_per_dataset_version(tables, make_agent, monkeypatch):
    calls = []
    real = agent_mod.profile_table
    monkeypatch.setattr(agent_mod, "profile_table", lambda t: (calls.append(t.name), real(t))[1])
    a = make_agent(FakeLLM())
    a.analyze(Q, tables)
    a.analyze(Q, tables)
    assert sorted(calls) == ["costs.csv", "products.xlsx", "sales.csv"]          # 3 tables, profiled once across 2 questions
    tables["sales.csv"].df = tables["sales.csv"].df.assign(Revenue=1)             # dataset content changed -> re-profile
    a.analyze(Q, tables)
    assert calls.count("sales.csv") == 2 and calls.count("costs.csv") == 1


def test_answers_are_never_cached_by_question_text(tables, make_agent):
    a = make_agent(FakeLLM())
    r1 = a.analyze(Q, tables)
    tables["costs.csv"].df = tables["costs.csv"].df.assign(Cost=0)
    r2 = a.analyze(Q, tables)
    assert r1.structured_result.value == 1240000.0 and r2.structured_result.value != r1.structured_result.value


def test_content_hash_and_load_bytes():
    data = (SAMPLE / "sales.csv").read_bytes()
    assert content_hash(data) == content_hash(bytes(data)) != content_hash(data + b"\n")
    t, skipped = load_bytes("sales.csv", data)
    assert "sales.csv" in t and not skipped
    t, skipped = load_bytes("x.pdf", b"%PDF")
    assert not t and "PDF support is not yet enabled" in skipped[0]


# ---- SAFE / WARNING / BLOCKING ----
def test_issue_severities(edge, tables, make_agent):
    r = make_agent(FakeLLM()).analyze(Q, tables)
    assert {i.severity for i in r.issues} == {Severity.SAFE}
    t = edge("sales_duplicates.csv", "costs.csv")
    dedup = PROFIT_CODE.replace("sales_df.groupby", "sales_duplicates_df.drop_duplicates().groupby")
    r = make_agent(FakeLLM(sources=("sales_duplicates.csv", "costs.csv"), code=dedup)).analyze(Q, t)
    assert r.status == Status.VERIFIED and any(i.severity == Severity.WARNING and i.kind == "duplicates_handled" for i in r.issues)
    raw = PROFIT_CODE.replace("sales_df", "sales_duplicates_df")
    r = make_agent(FakeLLM(sources=("sales_duplicates.csv", "costs.csv"), code=raw)).analyze(Q, t)
    assert r.status == Status.CANNOT_DETERMINE and any(i.severity == Severity.BLOCKING for i in r.issues)


def test_blocking_issue_can_never_be_verified(edge, make_agent):
    t = edge("report_conflict.xlsx", "sales_summary.xlsx")
    code = ('print(json.dumps({"result_type":"aggregate","metric":"revenue","operation":"sum",'
            '"value":float(report_conflict_df.Revenue.sum()+sales_summary_df.Revenue.sum())}))')
    r = make_agent(FakeLLM(sources=("report_conflict.xlsx", "sales_summary.xlsx"), code=code, answer="The total revenue was 525,000.")
                   ).analyze("What was the total revenue?", t)
    assert r.status == Status.CANNOT_DETERMINE and r.llm_calls == 1


# ---- UI honesty ----
def test_ui_does_not_advertise_pdf():
    from streamlit.testing.v1 import AppTest
    import os
    at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "..", "frontend", "streamlit_app.py"), default_timeout=60).run()
    src = open(os.path.join(os.path.dirname(__file__), "..", "frontend", "streamlit_app.py"), encoding="utf-8").read()
    assert 'type=["csv", "xlsx"]' in src and "PDF is not supported yet" in src


# ---- data-quality row accounting (computed by the application) ----
def test_dq_records_duplicates(edge, make_agent):
    t = edge("sales_duplicates.csv", "costs.csv")
    dedup = PROFIT_CODE.replace("sales_df.groupby", "sales_duplicates_df.drop_duplicates().groupby")
    r = make_agent(FakeLLM(sources=("sales_duplicates.csv", "costs.csv"), code=dedup)).analyze(Q, t)
    rec = next(x for x in r.evidence.data_quality_records if x.table == "sales_duplicates.csv")
    assert (rec.original_rows, rec.duplicate_rows_detected, rec.duplicate_rows_removed, rec.rows_used) == (277, 37, 37, 240)
    clean = next(x for x in r.evidence.data_quality_records if x.table == "costs.csv")
    assert clean.duplicate_rows_detected == 0 and clean.rows_used == clean.original_rows


def test_dq_records_missing_rows_excluded(edge, make_agent):
    t = edge("sales_missing.csv", "costs.csv")
    code = PROFIT_CODE.replace("sales_df.groupby", 'sales_missing_df.dropna(subset=["Revenue"]).groupby')
    s = pd.read_csv(SAMPLE.parent / "edge_cases" / "sales_missing.csv").dropna(subset=["Revenue"])
    c = pd.read_csv(SAMPLE / "costs.csv")
    p = (s.groupby("Product").Revenue.sum() - c.groupby("Product").Cost.sum()).sort_values(ascending=False)
    claim = AnswerClaim(answer=f"{p.index[0]} had the highest profit: {int(p.iloc[0]):,}.", claimed_entity=p.index[0])
    r = make_agent(FakeLLM(sources=("sales_missing.csv", "costs.csv"), code=code, answer=claim)).analyze(Q, t)
    rec = next(x for x in r.evidence.data_quality_records if x.table == "sales_missing.csv")
    assert rec.missing == {"Revenue": {"missing": 10, "rows_excluded": 10}} and rec.rows_used == 230 and rec.original_rows == 240


# ---- FINAL ANSWER RULE: app-built from the verified structured result; LLM = wording only ----
def test_final_answer_is_injected_from_verified_result_not_from_gemini_wording(tables, make_agent):
    wording = AnswerClaim(answer="Laptop Pro came out on top; its profit was 1,240,000 in INR terms.",
                          claimed_entity="Laptop Pro", claimed_value=1240000.0, claimed_unit="INR")
    r = make_agent(FakeLLM(answer=wording)).analyze(Q, tables)
    assert r.status == Status.VERIFIED
    assert r.answer == "Laptop Pro had the highest profit: ₹1,240,000."       # injected by the application
    assert r.explanation == wording.answer and r.answer != r.explanation       # LLM's text is separate wording


def test_gemini_cannot_change_verified_fields(tables, make_agent):
    for lie in [AnswerClaim(answer="Phone X had the highest profit: ₹800,000.", claimed_entity="Phone X"),
                AnswerClaim(answer="Laptop Pro made ₹9,99,999.", claimed_entity="Laptop Pro", claimed_value=999999.0),
                AnswerClaim(answer="Laptop Pro made $1,240,000.", claimed_unit="USD")]:
        r = make_agent(FakeLLM(answer=lie)).analyze(Q, tables)
        assert r.status == Status.NOT_VERIFIED and r.answer == "" and r.explanation == ""
        assert r.structured_result.selected_entity == "Laptop Pro" and r.structured_result.value == 1240000.0


@pytest.mark.parametrize("sr,expected", [
    (dict(result_type="aggregate", metric="revenue", operation="mean", value=842000.5, unit="INR"), "The mean of revenue was ₹842,000.5."),
    (dict(result_type="comparison", metric="revenue", entities=["North", "South"], values={"North": 500000.0, "South": 700000.0}, unit="INR"),
     "Comparison of revenue: North = ₹500,000; South = ₹700,000."),
])
def test_answer_injects_operation_and_comparison_values(sr, expected):
    assert render_answer(StructuredResult(**sr)) == expected


def test_report_fails_closed_without_verified_result():
    from backend.models.schemas import AnalysisReport
    # VERIFIED claimed but no structured result -> downgraded, answer stripped
    r = AnalysisReport(question="q", status=Status.VERIFIED, answer="Laptop Pro had the highest profit", explanation="x")
    assert r.status == Status.NOT_VERIFIED and r.answer == "" and r.explanation == ""
    # a non-verified status can never carry a confident answer
    r = AnalysisReport(question="q", status=Status.NOT_VERIFIED, answer="Phone X won")
    assert r.answer == ""
    r = AnalysisReport(question="q", status=Status.CANNOT_DETERMINE, answer="Phone X won")
    assert r.answer == ""
    assert AnalysisReport(question="q", status=Status.CANNOT_DETERMINE, answer="I cannot determine this from the provided data."
                          ).answer.startswith("I cannot")


def test_ui_hides_answer_when_not_verified(tables, make_agent):
    import os
    from streamlit.testing.v1 import AppTest
    src = open(os.path.join(os.path.dirname(__file__), "..", "frontend", "streamlit_app.py"), encoding="utf-8").read()
    assert "report.status == Status.VERIFIED and report.structured_result is not None" in src
    assert "No verified answer is available" in src
