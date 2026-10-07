"""Lightweight retrieval: question -> relevant file/sheet -> relevant columns.
Uses file/sheet names, column names, column types, simple synonyms and categorical value matching. No embeddings."""
import re
from dataclasses import dataclass, field

SYNONYMS = {
    "profit": {"revenue", "cost", "sale", "expense", "price"}, "margin": {"revenue", "cost", "sale", "expense"},
    "income": {"revenue", "sale"}, "earning": {"revenue", "sale"}, "turnover": {"revenue", "sale"},
    "spend": {"cost", "expense"}, "expense": {"cost"}, "sale": {"revenue", "unit"},
}
_DATE_HINT = re.compile(r"\b(19|20)\d{2}\b|\bq[1-4]\b|month|quarter|year|date|daily|weekly|monthly")


def _tok(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", str(text).lower()):
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


@dataclass
class RetrievedTable:
    name: str
    score: int
    reasons: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)


def retrieve(question: str, tables: dict, profiles: dict) -> list[RetrievedTable]:
    q = _tok(question)
    for w in list(q):
        q |= SYNONYMS.get(w, set())
    qlow = question.lower()
    scored: list[RetrievedTable] = []
    for name, t in tables.items():
        rt = RetrievedTable(name, 0)
        stem_tokens = _tok(t.source_file.rsplit(".", 1)[0]) | (_tok(t.sheet) if t.sheet else set())
        hit = q & stem_tokens
        if hit:
            rt.score += 2 * len(hit)
            rt.reasons.append(f"file/sheet name matches {sorted(hit)}")
        for cp in profiles[name].columns:
            ct = _tok(cp.name)
            if q & ct:
                rt.score += 3
                rt.columns.append(cp.name)
                rt.reasons.append(f"column '{cp.name}' matches question")
            elif cp.likely_date and _DATE_HINT.search(qlow):
                rt.score += 1
                rt.columns.append(cp.name)
                rt.reasons.append(f"date column '{cp.name}' (question mentions a time period)")
            if not cp.likely_numeric and not cp.likely_date and 0 < cp.unique <= 200:   # entity/value matching
                vals = {str(v) for v in t.df[cp.name].dropna().unique()}
                found = [v for v in vals if len(v) > 2 and re.search(rf"\b{re.escape(v.lower())}\b", qlow)]
                if found:
                    rt.score += 3
                    if cp.name not in rt.columns:
                        rt.columns.append(cp.name)
                    rt.reasons.append(f"value {sorted(found)[:2]} found in column '{cp.name}'")
        scored.append(rt)
    chosen = sorted([r for r in scored if r.score > 0], key=lambda r: -r.score)
    if not chosen:  # nothing matched: do not hide anything
        return [RetrievedTable(n, 0, ["no keyword match - all tables kept"], []) for n in tables]
    names = {r.name for r in chosen}
    for r in chosen:  # join keys between shortlisted tables are relevant too
        for other in chosen:
            if other.name != r.name:
                shared = {c.name for c in profiles[r.name].columns} & {c.name for c in profiles[other.name].columns}
                for c in sorted(shared):
                    if c not in r.columns and len(names) > 1:
                        r.columns.append(c)
    return chosen
