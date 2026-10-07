from backend.analysis.data_profiler import profile_table
from backend.analysis.schema_analyzer import describe_schema
from backend.models.schemas import Status
from backend.retrieval.retriever import retrieve
from conftest import FakeLLM


def _profiles(tables):
    return {n: profile_table(t) for n, t in tables.items()}


def test_retrieval_profit_pulls_sales_and_costs(tables):
    names = [r.name for r in retrieve("Which product generated the highest profit?", tables, _profiles(tables))]
    assert {"sales.csv", "costs.csv"} <= set(names)


def test_retrieval_by_name_value_and_column(tables):
    r = retrieve("Which category performed best?", tables, _profiles(tables))
    assert r[0].name == "products.xlsx" and "Category" in r[0].columns
    r = retrieve("revenue of the North region", tables, _profiles(tables))
    assert r[0].name == "sales.csv" and any("North" in x for x in r[0].reasons)


def test_retrieval_never_hides_data_when_nothing_matches(tables):
    assert len(retrieve("who is the CEO", tables, _profiles(tables))) == 3


def test_schema_text_lists_hidden_tables_by_name(tables):
    p = _profiles(tables)
    text = describe_schema(tables, p, only={"products.xlsx"})
    assert "OTHER AVAILABLE TABLES" in text and "sales.csv" in text and "TABLE 'sales.csv'" not in text


def test_provenance_reflects_what_actually_ran(tables, make_agent):
    code = ('d = sales_df.merge(costs_df.groupby("Product", as_index=False)["Cost"].sum(), on="Product")\n'
            'd = d[d["Region"] == "North"]\nd["Profit"] = d["Revenue"] - d["Cost"]\n'
            'g = d.groupby("Product")["Profit"].sum()\n'
            'print(json.dumps({"result_type":"ranking","metric":"profit","selected_entity":str(g.idxmax()),"value":float(g.max()),'
            '"direction":"highest","values":{str(k):float(v) for k,v in g.items()}}))')
    llm = FakeLLM(code=code)
    r = make_agent(llm).analyze("Which product has the highest profit in North?", tables)
    ev = r.evidence
    assert ev.files_used == ["costs.csv", "sales.csv"] and ev.tables_used == ["sales.csv", "costs.csv"]
    assert ev.columns_used["sales.csv"] == ["Product", "Region", "Revenue"]
    assert any("merge" in j and "on='Product'" in j for j in ev.joins)
    assert any("Region" in f and "North" in f for f in ev.filters)
    assert "derived column: Profit = d['Revenue'] - d['Cost']" in ev.transformations
    assert ev.planned_operations == ["compute"]             # model intent is kept separate from what really ran
    assert ev.code == r.code and len(ev.code_sha256) == 64 and ev.execution_output == r.execution.stdout
    assert set(ev.data_fingerprints) == {"sales.csv", "costs.csv"} and ev.retrieval
    assert ev.verification_status == r.status.value and ev.structured_result == r.structured_result


def test_provenance_does_not_fabricate_unused_sources(tables, make_agent):
    r = make_agent(FakeLLM(sources=("sales.csv", "costs.csv", "products.xlsx"))).analyze("Which product generated the highest profit?", tables)
    assert r.status == Status.VERIFIED and "products.xlsx" not in r.evidence.files_used   # planned but never used


def test_xlsx_sheet_recorded(tables, make_agent):
    code = ('print(json.dumps({"result_type":"aggregate","metric":"products","operation":"count","value":float(len(products_df))}))')
    r = make_agent(FakeLLM(sources=("products.xlsx",), code=code, answer="There are 5 products in the count.")).analyze(
        "What is the count of products?", tables)
    assert r.evidence.sheets_used == ["products.xlsx::Sheet1"]
