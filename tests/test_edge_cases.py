import pandas as pd
from backend.models.schemas import Status
from conftest import FakeLLM, SAMPLE


def test_demo1_highest_profit_verified(tables, make_agent):
    r = make_agent(FakeLLM()).analyze("Which product generated the highest profit and what was the profit?", tables)
    assert r.status == Status.VERIFIED
    assert '"Laptop Pro"' in r.execution.stdout and "1240000" in r.execution.stdout
    assert set(r.evidence.files_used) == {"sales.csv", "costs.csv"}
    assert r.evidence.columns_used["sales.csv"] == ["Product", "Revenue"]
    assert r.audit_id and r.stages[-1] == "Verifying result"


def test_demo2_unknown_year_never_calls_llm(tables, make_agent):
    llm = FakeLLM()
    r = make_agent(llm).analyze("What was the profit in 2035?", tables)
    assert r.status == Status.CANNOT_DETERMINE and "2035" in r.reason and llm.calls == []
    assert r.answer == "I cannot determine this from the provided data."


def test_invalid_question(tables, make_agent):
    r = make_agent(FakeLLM(answerable=False, reason="Not about the data")).analyze("What is the meaning of life?", tables)
    assert r.status == Status.CANNOT_DETERMINE and r.reason == "Not about the data"


def test_missing_source_file(tables, make_agent):
    r = make_agent(FakeLLM(sources=("inventory.csv",))).analyze("Stock levels?", tables)
    assert r.status == Status.CANNOT_DETERMINE and "inventory.csv" in r.reason


def test_generated_code_failure(tables, make_agent):
    r = make_agent(FakeLLM(code="print(1/0)")).analyze("Which product has the highest profit?", tables)
    assert r.status == Status.EXECUTION_FAILED


def test_failure_then_repair(tables, make_agent):
    from conftest import PROFIT_CODE
    r = make_agent(FakeLLM(codes=["print(nope_df)", PROFIT_CODE])).analyze("Which product has the highest profit?", tables)
    assert r.status == Status.VERIFIED


def test_unsafe_code_rejected(tables, make_agent):
    r = make_agent(FakeLLM(code="import os\nprint(os.environ)")).analyze("highest profit?", tables)
    assert r.status == Status.EXECUTION_FAILED and r.execution.blocked_reasons


def test_model_answer_disagrees_with_execution(tables, make_agent):
    r = make_agent(FakeLLM(answer="Phone X had the highest profit: ₹2,40,000.")).analyze("Which product has the highest profit?", tables)
    assert r.status == Status.NOT_VERIFIED


def test_group_by_region_revenue(tables, make_agent):
    code = 'g = sales_df.groupby("Region")["Revenue"].sum().sort_values(ascending=False)\nprint(json.dumps({"result_type": "ranking", "metric": "revenue", "selected_entity": str(g.index[0]), "value": float(g.iloc[0]), "direction": "highest", "values": {str(k): float(v) for k, v in g.items()}}))'
    s = pd.read_csv(SAMPLE / "sales.csv").groupby("Region").Revenue.sum().sort_values(ascending=False)
    ans = f"{s.index[0]} generated the highest revenue: {int(s.iloc[0])}."
    r = make_agent(FakeLLM(sources=("sales.csv",), code=code, answer=ans)).analyze("Which region generated the highest revenue?", tables)
    assert r.status == Status.VERIFIED


def test_q3_average_filter_by_date(tables, make_agent):
    code = ('d = sales_df.copy()\nd["Date"] = pd.to_datetime(d["Date"], format="%Y-%m-%d")\n'
            'q3 = d[d["Date"].dt.quarter == 3]\nprint(json.dumps({"result_type": "aggregate", "metric": "revenue", "operation": "mean", "value": round(float(q3["Revenue"].mean()), 2), "rows_used": int(len(q3))}))')
    s = pd.read_csv(SAMPLE / "sales.csv"); s = s[pd.to_datetime(s.Date).dt.quarter == 3]
    ans = f"The average revenue in Q3 was {round(s.Revenue.mean(), 2)}."
    r = make_agent(FakeLLM(sources=("sales.csv",), code=code, answer=ans)).analyze("What was the average revenue in Q3?", tables)
    assert r.status == Status.VERIFIED


def test_multi_table_join_with_category(tables, make_agent):
    code = ('m = sales_df.merge(products_df, on="Product")\ng = m.groupby("Category")["Revenue"].sum().sort_values(ascending=False)\n'
            'print(json.dumps({"result_type": "ranking", "metric": "revenue", "selected_entity": str(g.index[0]), "value": float(g.iloc[0]), "direction": "highest", "values": {str(k): float(v) for k, v in g.items()}}))')
    s = pd.read_csv(SAMPLE / "sales.csv").merge(pd.read_excel(SAMPLE / "products.xlsx"), on="Product")
    g = s.groupby("Category").Revenue.sum().sort_values(ascending=False)
    r = make_agent(FakeLLM(sources=("sales.csv", "products.xlsx"), code=code, answer=f"{g.index[0]} performed best with revenue {int(g.iloc[0])}.")
                   ).analyze("Which category performed best?", tables)
    assert r.status == Status.VERIFIED and set(r.evidence.files_used) == {"sales.csv", "products.xlsx"}
