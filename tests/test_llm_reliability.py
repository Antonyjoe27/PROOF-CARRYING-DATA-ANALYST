"""OpenRouter client + failure handling: config, bounded fallback, distinct statuses, no secrets in logs. Offline (fake `openai`)."""
import logging
import sys
import types as pytypes

import pytest

from backend.llm.errors import AIServiceUnavailable, LLMRequestError, classify
from backend.models.schemas import AnswerClaim, PlanAndCode, Status
from conftest import FakeLLM, PROFIT_CODE

Q = "Which product has the highest profit?"
SECRET = "sk-or-v1-SUPER-SECRET-KEY-123"


class HTTPErr(Exception):
    """Shape of openai.APIStatusError (status_code)."""
    def __init__(self, status_code, msg="boom"):
        super().__init__(f"Error code: {status_code} - {msg}")
        self.status_code = status_code


E503 = lambda: HTTPErr(503, "Provider returned error: high demand")
PLAN = PlanAndCode(answerable=True, reason="", sources=["sales.csv", "costs.csv"], columns=[], operation="compute",
                   transformations=["compute"], code=PROFIT_CODE)


def reply(text):
    msg = pytypes.SimpleNamespace(content=text)
    return pytypes.SimpleNamespace(choices=[pytypes.SimpleNamespace(message=msg)])


GOOD = lambda: reply("```json\n" + PLAN.model_dump_json() + "\n```")        # fenced JSON must be tolerated


@pytest.fixture
def fake_openai(monkeypatch):
    calls, ctor = [], {}

    def install(script):
        class Completions:
            def create(self, model, messages, temperature):
                calls.append(model)
                out = script[model].pop(0) if len(script[model]) > 1 else script[model][0]
                if isinstance(out, Exception):
                    raise out
                return out

        class OpenAI:
            def __init__(self, base_url=None, api_key=None, max_retries=None, default_headers=None):
                ctor.update(base_url=base_url, api_key=api_key, max_retries=max_retries)
                self.chat = pytypes.SimpleNamespace(completions=Completions())
        mod = pytypes.ModuleType("openai")
        mod.OpenAI = OpenAI
        monkeypatch.setitem(sys.modules, "openai", mod)
        return calls, ctor
    return install


def client(**kw):
    from backend.llm.openrouter import OpenRouterClient
    kw.setdefault("api_key", SECRET)
    kw.setdefault("model", "primary")
    kw.setdefault("fallback_models", ["fb1", "fb2"])
    return OpenRouterClient(**kw)


# ---- configuration ----
def test_uses_openrouter_base_url_and_env_config(fake_openai, monkeypatch):
    _, ctor = fake_openai({"anthropic/claude-sonnet-4.6": [GOOD()]})
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)         # a Gemini key is NOT required
    from backend.llm.openrouter import OpenRouterClient
    c = OpenRouterClient()
    assert ctor["base_url"] == "https://openrouter.ai/api/v1" and ctor["api_key"] == SECRET
    assert c.models == ["anthropic/claude-sonnet-4.6"]          # no fallbacks unless configured
    assert c.generate_structured("p", PlanAndCode).answerable


def test_missing_key_message_mentions_openrouter_not_gemini(fake_openai, monkeypatch):
    fake_openai({})
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from backend.llm.openrouter import OpenRouterClient
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set") as ei:
        OpenRouterClient(api_key=None)
    assert "gemini" not in str(ei.value).lower()


# ---- bounded fallback ----
def test_primary_succeeds_no_fallback(fake_openai):
    calls, _ = fake_openai({"primary": [GOOD()], "fb1": [GOOD()]})
    client().generate_structured("p", PlanAndCode)
    assert calls == ["primary"]


def test_503_then_fallback_succeeds_and_notifies(fake_openai):
    calls, _ = fake_openai({"primary": [E503()], "fb1": [GOOD()], "fb2": [GOOD()]})
    c, msgs = client(), []
    c.notify = msgs.append
    assert c.generate_structured("p", PlanAndCode).answerable
    assert calls == ["primary", "fb1"] and msgs == ["The AI model is temporarily unavailable. Trying a fallback model..."]


def test_two_503s_then_second_fallback(fake_openai):
    calls, _ = fake_openai({"primary": [E503()], "fb1": [E503()], "fb2": [GOOD()]})
    client().generate_structured("p", PlanAndCode)
    assert calls == ["primary", "fb1", "fb2"]


def test_all_503_each_model_once(fake_openai):
    calls, _ = fake_openai({"primary": [E503()], "fb1": [E503()], "fb2": [E503()]})
    with pytest.raises(AIServiceUnavailable):
        client().generate_structured("p", PlanAndCode)
    assert calls == ["primary", "fb1", "fb2"]


@pytest.mark.parametrize("err", [HTTPErr(401, f"No auth {SECRET}"), HTTPErr(402, "credits"), HTTPErr(400, "bad"), HTTPErr(429, "rate")])
def test_non_availability_errors_do_not_fall_back(fake_openai, err):
    calls, _ = fake_openai({"primary": [err], "fb1": [GOOD()]})
    with pytest.raises(LLMRequestError) as ei:
        client().generate_structured("p", PlanAndCode)
    assert calls == ["primary"] and SECRET not in str(ei.value)


def test_malformed_output_does_not_fall_back(fake_openai):
    calls, _ = fake_openai({"primary": [reply("not json at all")], "fb1": [GOOD()]})
    with pytest.raises(ValueError):
        client().generate_structured("p", PlanAndCode)
    assert calls == ["primary"]


def test_classify():
    assert classify(E503())[0] == "unavailable" and classify(HTTPErr(429))[0] == "other"


# ---- agent statuses ----
class OutageLLM(FakeLLM):
    def generate_structured(self, prompt, schema):
        self.calls.append(schema.__name__)
        raise AIServiceUnavailable([{"model": "primary", "http_status": 503}])


def test_outage_is_ai_service_unavailable(tables, make_agent):
    llm = OutageLLM()
    r = make_agent(llm).analyze(Q, tables)
    assert r.status == Status.AI_SERVICE_UNAVAILABLE and r.reason == "AI service is temporarily unavailable. Please retry."
    assert r.answer == "" and r.verification is None and r.execution is None and llm.calls == ["PlanAndCode"]


def test_rejected_key_is_planning_failed(tables, make_agent):
    r = make_agent(FakeLLM(fail_with=LLMRequestError("auth", 401, "HTTPErr"))).analyze(Q, tables)
    assert r.status == Status.PLANNING_FAILED and r.answer == "" and "gemini" not in r.reason.lower()


def test_cannot_determine_preserved(tables, make_agent):
    r = make_agent(FakeLLM()).analyze("What was the revenue in 2035?", tables)
    assert r.status == Status.CANNOT_DETERMINE and r.llm_calls == 0


def test_execution_failure_remains_execution_failed(tables, make_agent):
    assert make_agent(FakeLLM(codes=["print(1/0)", "print(2/0)"])).analyze(Q, tables).status == Status.EXECUTION_FAILED


def test_verification_failure_remains_not_verified(tables, make_agent):
    r = make_agent(FakeLLM(answer=AnswerClaim(answer="Phone X won.", claimed_entity="Phone X"))).analyze(Q, tables)
    assert r.status == Status.NOT_VERIFIED and r.answer == ""


def test_explanation_outage_never_weakens_verification(tables, make_agent):
    class ExplainDown(FakeLLM):
        def generate_structured(self, prompt, schema):
            if schema is AnswerClaim:
                raise AIServiceUnavailable([])
            return super().generate_structured(prompt, schema)
    r = make_agent(ExplainDown()).analyze(Q, tables)
    assert r.status == Status.VERIFIED and r.structured_result.selected_entity == "Laptop Pro"


# ---- no secrets in logs ----
def test_no_api_key_in_logs(fake_openai, caplog):
    fake_openai({"primary": [HTTPErr(503, f"key={SECRET}")], "fb1": [HTTPErr(401, f"key={SECRET}")]})
    with caplog.at_level(logging.DEBUG, logger="pcda.llm"):
        with pytest.raises(LLMRequestError):
            client(fallback_models=["fb1"]).generate_structured("confidential uploaded data", PlanAndCode)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "model=primary" in text and "http_status=503" in text and "fallback_used=True" in text and "ts=" in text
    assert SECRET not in caplog.text and "confidential uploaded data" not in text
