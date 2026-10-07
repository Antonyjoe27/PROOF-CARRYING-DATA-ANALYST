import pandas as pd


def load_excel(path) -> dict[str, pd.DataFrame]:
    """Return {sheet_name: DataFrame}. Values are loaded as-is (no silent cleaning)."""
    return pd.read_excel(path, sheet_name=None, engine="openpyxl")
