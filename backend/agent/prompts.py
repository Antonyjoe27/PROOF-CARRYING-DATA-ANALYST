PLAN_AND_CODE_PROMPT = """You are a careful data analyst. In ONE response, plan the analysis AND write the code.
You do not compute or state any answer yourself - the code will be executed and verified by Python.

{schema}

QUESTION: {question}

Plan fields:
- answerable=false (with a clear `reason`, and code="") if required data/columns/time periods do not exist, the tables
  cannot be joined to answer it, the calculation is unsupported, or the question is too ambiguous. Never guess.
- sources: exact TABLE names from above (e.g. 'sales.csv').
- columns: columns that ALREADY EXIST in those tables (exact names). derived_columns: columns your code will create
  (e.g. 'Profit'); never list derived columns in `columns`.
- operation: a short label (e.g. highest_profit). transformations: ordered plain-language steps (joins, filters, derived columns).

Code rules:
- DataFrames are already loaded as variables named above (e.g. `sales_df`). `pd`, `np`, `json`, `math` are preloaded.
- Allowed imports ONLY: pandas, numpy, math, json, datetime, re, statistics, decimal, collections.
- Do NOT read/write files, use the network, os/sys/subprocess, eval/exec/open, or dunder attributes.
- Do NOT use `.rename()` or filesystem/OS methods. To rename columns, assign directly to DataFrame columns or select directly.
- Deterministic; never hard-code answer values - compute everything from the data.
- Exact duplicate rows: call drop_duplicates() on any table you use that has them. Missing values: exclude explicitly
  with dropna(subset=[...columns you use]) - never silently ignore them.
- The LAST line must print ONE JSON object (single line) via print(json.dumps(result, default=str)).
  The result dictionary MUST include the key "result_type" set to "ranking", "aggregate", or "comparison":
  ranking   : {{"result_type":"ranking","metric":"profit","selected_entity":"Laptop Pro","value":1240000.0,"unit":"INR",
               "direction":"highest","values":{{"<entity>": <value>, ...for ALL entities}}}}
  aggregate : {{"result_type":"aggregate","metric":"revenue","operation":"mean","value":842000.0,"unit":"INR","rows_used":60}}
  comparison: {{"result_type":"comparison","entities":["North","South"],"metric":"revenue",
               "values":{{"North":500000.0,"South":700000.0}},"unit":"INR"}}
  Do NOT print custom keys like "Product" or "Total_Profit_INR" as top-level keys; use "result_type" and "selected_entity" / "value".
  `unit` is a currency code only if the data/question clearly implies one, otherwise "" (or e.g. "units").
  Use plain Python floats/strings (float(x), str(x)). "highest"/"lowest" must match the question."""

REPAIR_PROMPT = """Your previous code did not produce a valid verified result. Return a corrected version.

{schema}

QUESTION: {question}
PLAN: {operations}
PREVIOUS CODE:
{code}
PROBLEM (from the actual execution/verification):
{error}

Keep every rule from before: only the provided DataFrames, allowed imports only (pandas, numpy, math, json, datetime, re,
statistics, decimal, collections), no file/network/OS access, no .rename() (assign to .columns directly),
deterministic, handle duplicates with drop_duplicates() and missing values with dropna(subset=[...]) explicitly,
and finish with ONE print(json.dumps(result, default=str)) using the ranking/aggregate/comparison schema. Return only the corrected code in the `code` field."""

EXPLAIN_PROMPT = """The computation below has ALREADY been executed and independently verified. The application will display the
verified entity, value, unit and operation itself. You only provide a short WORDING/EXPLANATION of what the result means.

QUESTION: {question}
VERIFIED RESULT (JSON): {result}
{feedback}
Rules:
- Use ONLY facts in the verified result. Do not change, round differently, or add any number, entity or claim.
- Write numbers in full with thousands separators (no "lakh"/"million" words). Use a currency symbol only if `unit` is a currency.
- Also fill the claim fields to restate exactly what your text asserts: claimed_entity, claimed_value (plain number),
  claimed_unit, claimed_operation (e.g. mean/sum). Leave a field empty if your text makes no such claim.
- 1-3 sentences."""
