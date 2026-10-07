import re
import pandas as pd
from backend.models.schemas import ColumnProfile, DatasetProfile

_DATE_RE = re.compile(r"^\s*(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,4})\s*$")
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_UNITS = {
    "INR": ["₹", "inr", "rupee", "rs."], "USD": ["$", "usd", "dollar"], "EUR": ["€", "eur"],
    "kg": ["kg"], "%": ["%", "percent", "pct"],
}


def _is_textual(s: pd.Series) -> bool:
    return not pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_datetime64_any_dtype(s)


def _unit_hints(name: str, s: pd.Series) -> list[str]:
    hay = [name.lower()]
    if _is_textual(s):
        hay += [str(v).lower() for v in s.dropna().head(20)]
    text = " ".join(hay)
    return [u for u, toks in _UNITS.items() if any(t in text for t in toks)]


def _date_info(s: pd.Series, name: str):
    """Returns (likely_date, ambiguous, years)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return True, False, sorted({int(y) for y in s.dropna().dt.year.unique()})
    if not _is_textual(s):
        years = []
        if "year" in name.lower():
            vals = pd.to_numeric(s, errors="coerce").dropna()
            years = sorted({int(v) for v in vals if 1900 <= v <= 2100})
        return bool(years), False, years
    vals = [str(v) for v in s.dropna()]
    if not vals:
        return False, False, []
    parsed, years = [], set()
    for v in vals:
        m = _DATE_RE.match(v)
        if m:
            parsed.append(m.groups())
            years.update(int(y) for y in _YEAR_RE.findall(v))
    if len(parsed) / len(vals) >= 0.9:
        a_first_is_year = all(len(g[0]) == 4 for g in parsed)
        ambiguous = False
        if not a_first_is_year:
            a = [int(g[0]) for g in parsed]
            b = [int(g[1]) for g in parsed]
            ambiguous = max(a) <= 12 and max(b) <= 12 and any(x != y for x, y in zip(a, b))
        return True, ambiguous, sorted(years)
    if any(k in name.lower() for k in ("date", "month", "period")):
        found = {int(y) for v in vals for y in _YEAR_RE.findall(v)}
        if found:
            return True, False, sorted(found)
    return False, False, []


def profile_column(df: pd.DataFrame, name: str) -> ColumnProfile:
    s = df[name]
    likely_numeric = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
    text_numeric = False
    if _is_textual(s) and s.notna().any():
        cleaned = s.dropna().astype(str).str.replace(r"[,₹$€%\s]", "", regex=True)
        text_numeric = pd.to_numeric(cleaned, errors="coerce").notna().mean() >= 0.9
    is_date, ambiguous, years = _date_info(s, str(name))
    return ColumnProfile(
        name=str(name), dtype=str(s.dtype), missing=int(s.isna().sum()), unique=int(s.nunique(dropna=True)),
        likely_numeric=bool(likely_numeric or text_numeric), likely_date=is_date, ambiguous_date=ambiguous,
        years=years, unit_hints=_unit_hints(str(name), s),
    ), text_numeric


def profile_table(t) -> DatasetProfile:
    df = t.df
    cols, warnings = [], []
    dups = int(df.duplicated().sum())
    if dups:
        warnings.append(f"⚠ {dups} duplicate rows detected")
    for name in df.columns:
        cp, text_numeric = profile_column(df, name)
        cols.append(cp)
        if cp.missing:
            warnings.append(f"⚠ {cp.name} contains missing values ({cp.missing})")
        if cp.ambiguous_date:
            warnings.append(f"⚠ Date format in '{cp.name}' may be ambiguous (dd/mm vs mm/dd)")
        if text_numeric:
            warnings.append(f"⚠ '{cp.name}' looks numeric but is stored as text")
    return DatasetProfile(name=t.name, variable=t.variable, source_file=t.source_file, sheet=t.sheet,
                          rows=len(df), columns=cols, duplicate_rows=dups, warnings=warnings)


def cross_table_warnings(profiles: dict[str, DatasetProfile]) -> list[str]:
    out = []
    units = {n: {u for c in p.columns for u in c.unit_hints if u in ("INR", "USD", "EUR")} for n, p in profiles.items()}
    allu = set().union(*units.values()) if units else set()
    if len(allu) > 1:
        out.append("⚠ Currency/unit may differ across files: " + ", ".join(sorted(allu)))
    return out
