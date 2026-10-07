from backend.analysis.data_profiler import profile_table, cross_table_warnings
from backend.analysis.schema_analyzer import join_keys


def test_clean_profile(tables):
    p = profile_table(tables["sales.csv"])
    assert p.rows == 240 and p.duplicate_rows == 0 and p.warnings == []
    date = next(c for c in p.columns if c.name == "Date")
    assert date.likely_date and not date.ambiguous_date and date.years == [2025]


def test_duplicates_detected(edge):
    p = profile_table(edge("sales_duplicates.csv")["sales_duplicates.csv"])
    assert p.duplicate_rows == 37 and "⚠ 37 duplicate rows detected" in p.warnings


def test_missing_detected(edge):
    p = profile_table(edge("sales_missing.csv")["sales_missing.csv"])
    assert any("Revenue contains missing values" in w for w in p.warnings)


def test_ambiguous_dates_detected(edge):
    p = profile_table(edge("sales_ambiguous_dates.csv")["sales_ambiguous_dates.csv"])
    assert any("ambiguous" in w for w in p.warnings)


def test_join_keys(tables):
    profiles = {n: profile_table(t) for n, t in tables.items()}
    assert "Product" in join_keys(profiles)[("sales.csv", "costs.csv")]
    assert cross_table_warnings(profiles) == []
