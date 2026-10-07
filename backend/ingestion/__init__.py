import re
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

from .csv_loader import load_csv
from .excel_loader import load_excel
from .pdf_loader import load_pdf


@dataclass
class LoadedTable:
    name: str          # display/provenance name, e.g. "sales.csv" or "report.xlsx::Q1"
    variable: str      # python variable exposed to generated code, e.g. "sales_df"
    source_file: str
    sheet: str | None
    df: pd.DataFrame


def _var(text: str) -> str:
    v = re.sub(r"\W+", "_", text).strip("_").lower() or "data"
    if v[0].isdigit():
        v = "t_" + v
    return v + "_df"


def load_path(path) -> list[LoadedTable]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        return [LoadedTable(p.name, _var(p.stem), p.name, None, load_csv(p))]
    if ext in (".xlsx", ".xlsm"):
        sheets = load_excel(p)
        out = []
        for sheet, df in sheets.items():
            if len(sheets) == 1:
                out.append(LoadedTable(p.name, _var(p.stem), p.name, sheet, df))
            else:
                out.append(LoadedTable(f"{p.name}::{sheet}", _var(f"{p.stem}_{sheet}"), p.name, sheet, df))
        return out
    if ext == ".pdf":
        return load_pdf(p)  # raises NotImplementedError("PDF support is not yet enabled ...")
    raise ValueError(f"Unsupported file type: {p.suffix}")


def load_many(paths, skipped: list[str] | None = None) -> dict[str, LoadedTable]:
    """Load every supported file. Unsupported/unavailable files (e.g. PDF) never break the others; the reason is
    appended to `skipped` (if given) so the UI can report it."""
    tables: dict[str, LoadedTable] = {}
    for path in paths:
        try:
            for t in load_path(path):
                tables[t.name] = t
        except (NotImplementedError, ValueError) as e:
            if skipped is not None:
                skipped.append(f"{Path(path).name}: {e}")
    return tables


def content_hash(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def load_bytes(name: str, data: bytes) -> tuple[dict[str, LoadedTable], list[str]]:
    """Load an uploaded file from memory (used by the cached UI loader). Returns (tables, skipped_messages)."""
    import tempfile
    skipped: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / Path(name).name
        p.write_bytes(data)
        return load_many([p], skipped), skipped
