import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))
import generate_samples  # noqa: E402

from backend.agent.agent import DataAnalystAgent  # noqa: E402
from backend.ingestion import load_many  # noqa: E402
from backend.models.schemas import AnswerClaim, CodeResponse, PlanAndCode  # noqa: E402

generate_samples.main()
SAMPLE, EDGE = ROOT / "data/sample", ROOT / "data/edge_cases"
PROFIT_CODE = """
rev = sales_df.groupby("Product")["Revenue"].sum()
cost = costs_df.groupby("Product")["Cost"].sum()
profit = (rev - cost).sort_values(ascending=False)
result = {"result_type": "ranking", "metric": "profit", "selected_entity": str(profit.index[0]),
          "value": float(profit.iloc[0]), "unit": "INR", "direction": "highest",
          "values": {str(k): float(v) for k, v in profit.items()}}
print(json.dumps(result))
"""
GOOD_CLAIM = AnswerClaim(answer="Laptop Pro had the highest profit: ₹1,240,000.", claimed_entity="Laptop Pro",
                         claimed_value=1240000.0, claimed_unit="INR")


class FakeLLM:
    """Scripted stand-in for LLM so tests are offline and deterministic. Records every call by schema name."""
    def __init__(self, sources=("sales.csv", "costs.csv"), code=PROFIT_CODE, answer=None,
                 answerable=True, reason="", codes=None, required_columns=(), fail_with=None):
        self.answerable, self.reason, self.sources, self.required_columns = answerable, reason, list(sources), list(required_columns)
        self.codes, self.calls, self.fail_with = list(codes or [code]), [], fail_with
        # `answer` may be a str (text only), an AnswerClaim, or None (= GOOD_CLAIM)
        self.claim = GOOD_CLAIM if answer is None else (answer if isinstance(answer, AnswerClaim) else AnswerClaim(answer=answer))

    def _code(self):
        return self.codes.pop(0) if len(self.codes) > 1 else self.codes[0]

    def generate_structured(self, prompt, schema):
        self.calls.append(schema.__name__)
        if self.fail_with:
            raise self.fail_with
        if schema is PlanAndCode:
            return PlanAndCode(answerable=self.answerable, reason=self.reason, sources=self.sources,
                               columns=self.required_columns, operation="compute", transformations=["compute"],
                               code=self._code() if self.answerable else "")
        if schema is CodeResponse:
            return CodeResponse(code=self._code())
        return self.claim


@pytest.fixture
def tables():
    return load_many([SAMPLE / "sales.csv", SAMPLE / "costs.csv", SAMPLE / "products.xlsx"])


@pytest.fixture
def make_agent(tmp_path):
    return lambda llm: DataAnalystAgent(llm, outputs_dir=tmp_path, timeout=20)


@pytest.fixture
def edge():
    return lambda *names: load_many([EDGE / n if (EDGE / n).exists() else SAMPLE / n for n in names])
