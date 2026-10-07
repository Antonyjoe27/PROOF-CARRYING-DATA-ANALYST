"""End-to-end demo scenarios (FakeLLM stands in for LLM; execution, verification and provenance are real)."""
import json
import pandas as pd
from backend.ingestion import load_many, load_path
from backend.models.schemas import AnswerClaim, Status
from conftest import EDGE, FakeLLM, GOOD_CLAIM, PROFIT_CODE, SAMPLE

REGION_CODE = """
rev = sales_df.groupby("Region")["Revenue"].sum()
cost = costs_df.groupby("Region")["Cost"].sum()
profit = (rev - cost).sort_values(ascending=False)
print(json.dumps({"result_type": "ranking", "metric": "profit", "selected_entity": str(profit.index[0]),
                  "value": float(profit.iloc[0]), "direction": "highest", "values": {str(k): float(v) for k, v in profit.items()}}))
"""


def test_demo1_highest_profit(tables, make_agent):
    r = make_agent(FakeLLM()).analyze("Which product generated the highest profit?", tables)
    assert r.status == Status.VERIFIED and r.structured_result.selected_entity == "Laptop Pro"
    assert r.evidence.result_summary.startswith("Laptop Pro → ₹1,240,000")
    assert r.evidence.files_used == ["costs.csv", "sales.csv"] and r.evidence.columns_used["costs.csv"] == ["Product", "Cost"]
    assert r.verification.checks["answer_consistent_with_result"]


def test_demo2_region_profit_multi_table(tables, make_agent):
    s, c = pd.read_csv(SAMPLE / "sales.csv"), pd.read_csv(SAMPLE / "costs.csv")
    p = (s.groupby("Region").Revenue.sum() - c.groupby("Region").Cost.sum()).sort_values(ascending=False)
    claim = AnswerClaim(answer=f"{p.index[0]} generated the highest profit: {int(p.iloc[0]):,}.", claimed_entity=p.index[0], claimed_value=float(p.iloc[0]))
    r = make_agent(FakeLLM(code=REGION_CODE, answer=claim)).analyze(
        "Which region generated the highest profit after combining sales and costs?", tables)
    assert r.status == Status.VERIFIED and p.index[0] == "North" == r.structured_result.selected_entity
    assert set(r.evidence.files_used) == {"sales.csv", "costs.csv"}


def test_demo3_unanswerable_year(tables, make_agent):
    llm = FakeLLM()
    r = make_agent(llm).analyze("What was the company's revenue in 2035?", tables)
    assert r.status == Status.CANNOT_DETERMINE and r.reason == "No records for 2035 exist in the supplied data."
    assert llm.calls == [] and r.blocking_issues


def test_missing_column_abstains(tables, make_agent):
    llm = FakeLLM(required_columns=["Profit Margin"])
    r = make_agent(llm).analyze("What is the profit margin percentage?", tables)
    assert r.status == Status.CANNOT_DETERMINE and "Profit Margin" in r.reason and llm.calls == ["PlanAndCode"]


def test_demo4_conflicting_sources(edge, make_agent):
    t = edge("report_conflict.xlsx", "sales_summary.xlsx")
    code = ('a = report_conflict_df.set_index("Product")["Revenue"]\nb = sales_summary_df.set_index("Product")["Revenue"]\n'
            'print(json.dumps({"result_type":"comparison","entities":["a","b"],"metric":"revenue","values":{"a":float(a.sum()),"b":float(b.sum())}}))')
    r = make_agent(FakeLLM(sources=("report_conflict.xlsx", "sales_summary.xlsx"), code=code)).analyze("What was the total revenue?", t)
    assert r.status == Status.CANNOT_DETERMINE and "Conflicting sources" in r.reason and r.answer.startswith("I cannot determine")


def test_demo5_duplicates_documented_rule(edge, make_agent):
    t = edge("sales_duplicates.csv", "costs.csv")
    raw = PROFIT_CODE.replace("sales_df", "sales_duplicates_df")
    dedup = PROFIT_CODE.replace("sales_df.groupby", "sales_duplicates_df.drop_duplicates().groupby")
    # without handling -> blocking
    r = make_agent(FakeLLM(sources=("sales_duplicates.csv", "costs.csv"), code=raw)).analyze("Which product has the highest profit?", t)
    assert r.status == Status.CANNOT_DETERMINE and "duplicate" in r.reason
    # the agent asks for ONE regeneration that applies the documented rule -> verified, and it is recorded
    r = make_agent(FakeLLM(sources=("sales_duplicates.csv", "costs.csv"), codes=[raw, dedup])).analyze("Which product has the highest profit?", t)
    assert r.status == Status.VERIFIED and r.structured_result.value == 1240000.0
    assert any("37 exact duplicate rows dropped" in a for a in r.evidence.data_quality_actions)
    assert "exact duplicate rows removed" in r.evidence.transformations


def test_missing_values_handled_explicitly(edge, make_agent):
    t = edge("sales_missing.csv", "costs.csv")
    code = PROFIT_CODE.replace("sales_df.groupby", 'sales_missing_df.dropna(subset=["Revenue"]).groupby')
    s = pd.read_csv(EDGE / "sales_missing.csv").dropna(subset=["Revenue"])
    c = pd.read_csv(SAMPLE / "costs.csv")
    p = (s.groupby("Product").Revenue.sum() - c.groupby("Product").Cost.sum()).sort_values(ascending=False)
    claim = AnswerClaim(answer=f"{p.index[0]} had the highest profit: {int(p.iloc[0]):,}.", claimed_entity=p.index[0], claimed_value=float(p.iloc[0]))
    r = make_agent(FakeLLM(sources=("sales_missing.csv", "costs.csv"), code=code, answer=claim)).analyze("Which product has the highest profit?", t)
    assert r.status == Status.VERIFIED
    assert any("missing values excluded with dropna" in a for a in r.evidence.data_quality_actions)
    unhandled = make_agent(FakeLLM(sources=("sales_missing.csv", "costs.csv"), code=PROFIT_CODE.replace("sales_df", "sales_missing_df"))
                           ).analyze("Which product has the highest profit?", t)
    assert unhandled.status == Status.CANNOT_DETERMINE and "missing values" in unhandled.reason


def test_ambiguous_dates_blocking(edge, make_agent):
    t = edge("sales_ambiguous_dates.csv")
    code = ('d = sales_ambiguous_dates_df.copy(); d["Date"] = pd.to_datetime(d["Date"])\n'
            'print(json.dumps({"result_type":"aggregate","metric":"revenue","operation":"sum","value":float(d["Revenue"].sum())}))')
    r = make_agent(FakeLLM(sources=("sales_ambiguous_dates.csv",), code=code)).analyze("What was the total revenue in March?", t)
    assert r.status == Status.CANNOT_DETERMINE and "ambiguous date" in r.reason


def test_demo6_wrong_answer_attack(tables, make_agent):
    for lie in [AnswerClaim(answer="Phone X had the highest profit: 800,000.", claimed_entity="Phone X", claimed_value=800000.0),
                AnswerClaim(answer="Laptop Pro had the highest profit: ₹1,240,000.", claimed_entity="Laptop Pro", claimed_value=999.0),
                AnswerClaim(answer="Laptop Pro had the highest profit: $1,240,000.", claimed_entity="Laptop Pro", claimed_value=1240000.0, claimed_unit="USD"),
                "Laptop Pro had the highest profit: 1,240,000, roughly 13 lakh."]:
        r = make_agent(FakeLLM(answer=lie)).analyze("Which product generated the highest profit?", tables)
        assert r.status == Status.NOT_VERIFIED and r.answer == "" and r.rejected_answer
        assert r.structured_result.selected_entity == "Laptop Pro"     # the computed result is untouched


def test_explanation_is_retried_once_with_feedback(tables, make_agent):
    class Flaky(FakeLLM):
        n = 0
        def generate_structured(self, prompt, schema):
            if schema is AnswerClaim:
                Flaky.n += 1
                return AnswerClaim(answer="Phone X won.", claimed_entity="Phone X") if Flaky.n == 1 else GOOD_CLAIM
            return super().generate_structured(prompt, schema)
    r = make_agent(Flaky()).analyze("Which product generated the highest profit?", tables)
    assert r.status == Status.VERIFIED and r.answer == GOOD_CLAIM.answer and r.explanation == GOOD_CLAIM.answer


def test_unverified_computation_is_never_explained(tables, make_agent):
    llm = FakeLLM(code='print("Laptop Pro 1240000")')
    r = make_agent(llm).analyze("Which product generated the highest profit?", tables)
    assert r.status == Status.NOT_VERIFIED and r.answer == "" and "AnswerClaim" not in llm.calls


def test_pdf_not_enabled_does_not_break_csv(tmp_path):
    pdf = tmp_path / "report.pdf"; pdf.write_bytes(b"%PDF-1.4")
    skipped = []
    t = load_many([SAMPLE / "sales.csv", pdf, SAMPLE / "products.xlsx"], skipped)
    assert set(t) == {"sales.csv", "products.xlsx"}
    assert len(skipped) == 1 and "PDF support is not yet enabled" in skipped[0]
    try:
        load_path(pdf)
        assert False
    except NotImplementedError as e:
        assert "PDF support is not yet enabled" in str(e)
