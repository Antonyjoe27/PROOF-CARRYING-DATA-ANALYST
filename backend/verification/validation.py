"""Deterministic data-quality / answerability checks (no LLM involved)."""
import ast
import re
import pandas as pd
from backend.analysis.query_analyzer import years_in_question


def unsupported_years(question: str, profiles) -> list[int]:
    available = {y for p in profiles.values() for c in p.columns for y in c.years}
    return [y for y in years_in_question(question) if y not in available]


def code_usage(code: str, tables) -> tuple[list[str], dict[str, list[str]]]:
    """Which tables/columns does the code ACTUALLY reference? (AST-derived, not LLM-claimed)"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [], {}
    names, strings = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            strings.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            strings.add(n.value)
    used = [name for name, t in tables.items() if t.variable in names]
    cols = {name: [str(x) for x in tables[name].df.columns if str(x) in strings] for name in used}
    return used, cols


def handles_duplicates(code: str) -> bool:
    return "drop_duplicates" in code


def handles_missing(code: str) -> bool:
    return bool(re.search(r"\b(dropna|fillna|isna|isnull|notna|notnull)\b", code))


def detect_conflicts(tables, names) -> list[str]:
    """Same key + same numeric column in two sources with different aggregated values."""
    out = []
    names = list(names)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            da, db = tables[a].df, tables[b].df
            shared = [c for c in da.columns if c in db.columns]
            keys = [c for c in shared if not pd.api.types.is_numeric_dtype(da[c]) and da[c].nunique() <= max(50, len(da) // 2)
                    and "date" not in str(c).lower()]
            nums = [c for c in shared if pd.api.types.is_numeric_dtype(da[c]) and pd.api.types.is_numeric_dtype(db[c])]
            for k in keys[:1]:
                for n in nums:
                    ga, gb = da.groupby(k)[n].sum(), db.groupby(k)[n].sum()
                    common = ga.index.intersection(gb.index)
                    diff = [str(x) for x in common if abs(ga[x] - gb[x]) > 1e-9]
                    if diff:
                        out.append(f"{a} and {b} disagree on '{n}' for {k} = {', '.join(diff[:3])}")
    return out


def impossible_joins(tables, names) -> list[str]:
    """Two used tables share text key column(s) but NO key value overlaps -> a join would be empty."""
    out = []
    names = list(names)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            da, db = tables[a].df, tables[b].df
            keys = [c for c in da.columns if c in db.columns and not pd.api.types.is_numeric_dtype(da[c])
                    and "date" not in str(c).lower()]
            if keys and all(not (set(da[k].dropna().astype(str)) & set(db[k].dropna().astype(str))) for k in keys):
                out.append(f"{a} and {b} share column(s) {keys} but have no matching values, so they cannot be joined")
    return out


def unit_mismatches(used, cols, profiles) -> list[str]:
    """Different currencies/units on the columns actually used from different tables."""
    seen: dict[str, set[str]] = {}
    for n in used:
        for cp in profiles[n].columns:
            if cp.name in cols.get(n, []):
                for u in cp.unit_hints:
                    if u in ("INR", "USD", "EUR"):
                        seen.setdefault(u, set()).add(f"{n}.{cp.name}")
    if len(seen) > 1:
        return ["Possible currency mismatch between used columns: " + "; ".join(f"{u}: {', '.join(sorted(v))}" for u, v in seen.items())]
    return []


def missing_columns(plan, tables) -> list[str]:
    """Columns the plan says it needs that exist in no required table (derived columns are exempt)."""
    srcs = [s for s in plan.required_sources if s in tables] or list(tables)
    have = {str(c).strip().lower() for s in srcs for c in tables[s].df.columns}
    derived = {d.strip().lower() for d in getattr(plan, "derived_columns", [])}
    return [c for c in plan.required_columns if c.strip().lower() not in have and c.strip().lower() not in derived]


def extract_joins(code: str) -> list[str]:
    out = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return out
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("merge", "join"):
            kw = {k.arg: ast.unparse(k.value) for k in n.keywords if k.arg in ("on", "left_on", "right_on", "how")}
            left = ast.unparse(n.func.value)
            right = ast.unparse(n.args[0]) if n.args else kw.get("right", "?")
            out.append(f"{left}.{n.func.attr}({right}" + "".join(f", {k}={v}" for k, v in kw.items()) + ")")
    return out


def extract_filters(code: str) -> list[str]:
    out = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return out
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and any(isinstance(x, (ast.Compare, ast.BoolOp)) for x in ast.walk(n.slice)):
            out.append(ast.unparse(n.slice))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "query" and n.args \
                and isinstance(n.args[0], ast.Constant):
            out.append(str(n.args[0].value))
    return list(dict.fromkeys(out))


def extract_derivations(code: str) -> list[str]:
    """e.g. `df["Profit"] = df["Revenue"] - df["Cost"]` -> 'Profit = ...'"""
    out = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return out
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Subscript) \
                and isinstance(n.targets[0].slice, ast.Constant) and isinstance(n.targets[0].slice.value, str):
            out.append(f"{n.targets[0].slice.value} = {ast.unparse(n.value)}")
    return out


def dq_record(table_name, df, code, used_cols):
    """Row accounting for one table, derived from the executed code. Applied to the table alone (before joins/filters)."""
    from backend.models.schemas import DataQualityRecord
    n0 = len(df)
    dups = int(df.duplicated().sum())
    dedup = handles_duplicates(code)
    subset_dedup = bool(re.search(r"drop_duplicates\(\s*[^)\s]", code))
    cur = df.drop_duplicates() if dedup else df
    removed = n0 - len(cur) if dedup else 0
    missing, note = {}, []
    if dedup and subset_dedup:
        note.append("drop_duplicates() used a subset/arguments; removed count is measured on the table")
    dropna_cols = None
    if re.search(r"\bdropna\b", code):
        try:
            tree = ast.parse(code)
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "dropna":
                    sub = next((k.value for k in n.keywords if k.arg == "subset"), None)
                    cols = [e.value for e in getattr(sub, "elts", []) if isinstance(e, ast.Constant)] if sub is not None else \
                        ([sub.value] if isinstance(sub, ast.Constant) else [])
                    dropna_cols = set(cols) if sub is not None else set(map(str, df.columns))
        except SyntaxError:
            pass
    excluded_mask = None
    if dropna_cols:
        present = [c for c in dropna_cols if c in cur.columns]
        excluded_mask = cur[present].isna().any(axis=1) if present else None
    for c in used_cols:
        if c in df.columns and df[c].isna().any():
            k = int(df[c].isna().sum())
            ex = int(cur[c].isna().sum()) if (excluded_mask is not None and c in dropna_cols) else 0
            missing[c] = {"missing": k, "rows_excluded": ex}
    rows_used = len(cur) - (int(excluded_mask.sum()) if excluded_mask is not None else 0)
    if re.search(r"\bfillna\b", code):
        note.append("fillna used: missing values were imputed, not excluded")
    return DataQualityRecord(table=table_name, original_rows=n0, duplicate_rows_detected=dups, duplicate_rows_removed=removed,
                             missing=missing, rows_used=rows_used, note="; ".join(note))
