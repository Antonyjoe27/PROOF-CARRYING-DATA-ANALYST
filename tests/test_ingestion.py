from backend.ingestion import load_many, load_path
import pytest


def test_loads_csv_and_xlsx(tables):
    assert set(tables) == {"sales.csv", "costs.csv", "products.xlsx"}
    assert tables["sales.csv"].variable == "sales_df"
    assert tables["products.xlsx"].variable == "products_df"
    assert len(tables["sales.csv"].df) == 240


def test_unsupported_type(tmp_path):
    p = tmp_path / "x.txt"; p.write_text("a")
    with pytest.raises(ValueError):
        load_path(p)
