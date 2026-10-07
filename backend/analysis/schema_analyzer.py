from backend.models.schemas import DatasetProfile


def join_keys(profiles: dict[str, DatasetProfile]) -> dict[tuple[str, str], list[str]]:
    names = list(profiles)
    out = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = sorted({c.name for c in profiles[a].columns} & {c.name for c in profiles[b].columns})
            if shared:
                out[(a, b)] = shared
    return out


def describe_schema(tables, profiles, only=None, relevant=None) -> str:
    """Compact schema text for LLM prompts. `only` limits detailed tables (others are listed by name+columns so
    nothing is hidden); `relevant` = {table: [columns]} marks retrieved columns."""
    parts = []
    shown = [n for n in tables if only is None or n in only]
    for name in shown:
        t = tables[name]
        p = profiles[name]
        cols = ", ".join(f"{c.name} ({c.dtype}{', date' if c.likely_date else ''})" for c in p.columns)
        sample = t.df.head(3).to_string(index=False)
        rel = f"  most relevant columns: {', '.join(relevant[name])}\n" if relevant and relevant.get(name) else ""
        parts.append(f"TABLE '{name}' -> python variable `{t.variable}` ({p.rows} rows)\n  columns: {cols}\n{rel}"
                     f"  sample rows:\n" + "\n".join("    " + ln for ln in sample.splitlines()))
        if p.warnings:
            parts.append("  data-quality warnings: " + "; ".join(p.warnings))
    hidden = [n for n in tables if n not in shown]
    if hidden:
        parts.append("OTHER AVAILABLE TABLES (less likely relevant): " + "; ".join(
            f"'{n}' (`{tables[n].variable}`: {', '.join(c.name for c in profiles[n].columns)})" for n in hidden))
    jk = {k: v for k, v in join_keys(profiles).items() if k[0] in shown and k[1] in shown}
    if jk:
        parts.append("POSSIBLE JOIN KEYS: " + "; ".join(f"{a} <-> {b} on {k}" for (a, b), k in jk.items()))
    return "\n".join(parts)
