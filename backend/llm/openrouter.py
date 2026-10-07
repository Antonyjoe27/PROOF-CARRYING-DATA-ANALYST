"""OpenRouter client (OpenAI-compatible API). The LLM only PROPOSES plans/code/wording; Python execution and the
deterministic verifier remain the source of truth. The API key is read from the environment only and is never logged."""
import json
import logging
import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv

from .errors import (UNAVAILABLE, USER_FALLBACK_MSG, AIServiceUnavailable, LLMRequestError, classify)

load_dotenv()
BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_SDK_RETRIES = 2         # the OpenAI SDK's own retry (transient errors); the ONLY retry layer

log = logging.getLogger("pcda.llm")


def _parse_models(raw: str | None) -> list[str]:
    return [m.strip() for m in (raw or "").split(",") if m.strip()]


def extract_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating ```json fences or short surrounding prose."""
    t = (text or "").strip()
    if not t:
        raise ValueError("empty response")
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I).strip()
    try:
        return json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            raise ValueError("response is not JSON")
        return json.loads(t[a:b + 1])


class OpenRouterClient:
    """Thin wrapper over the official `openai` SDK pointed at OpenRouter.

    Bounded behaviour: one application-level attempt per model; the SDK retries transient errors inside it. A fallback model
    (OPENROUTER_FALLBACK_MODELS, empty by default) is tried only after a final 503. Auth/credit/bad-request errors never fall back.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None, fallback_models=None, max_retries=None):
        key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key.")
        from openai import OpenAI
        self.model = model or os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL
        fb = fallback_models if fallback_models is not None else _parse_models(os.getenv("OPENROUTER_FALLBACK_MODELS"))
        self.models = [self.model, *[m for m in dict.fromkeys(fb) if m != self.model]]
        retries = int(max_retries if max_retries is not None else os.getenv("OPENROUTER_MAX_RETRIES", DEFAULT_SDK_RETRIES))
        self._client = OpenAI(base_url=BASE_URL, api_key=key, max_retries=max(0, retries),
                              default_headers={"X-Title": "Proof-Carrying Data Analyst"})
        self.notify = None              # optional callable(str): user-facing progress message
        self.attempt_log: list[dict] = []

    def _record(self, model, error_type, status, fallback_used, outcome):
        rec = {"model": model, "error_type": error_type, "http_status": status, "fallback_used": fallback_used,
               "outcome": outcome, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.attempt_log.append(rec)
        if outcome == "ok":       # metadata only: never prompts, uploaded data, response bodies, exception text or credentials
            log.info("llm_attempt model=%s outcome=ok fallback_used=%s ts=%s", model, fallback_used, rec["timestamp"])
        else:
            log.warning("llm_attempt model=%s outcome=%s error_type=%s http_status=%s fallback_used=%s ts=%s", model, outcome,
                        error_type, status, fallback_used, rec["timestamp"])

    def _with_fallback(self, call):
        failures = []
        for i, model in enumerate(self.models):
            try:
                result = call(model)
            except Exception as e:
                if isinstance(e, (ValueError, KeyError, TypeError)):
                    raise                                   # malformed output: the agent's single retry handles it
                kind, status = classify(e)
                self._record(model, type(e).__name__, status, i > 0, kind)
                if kind != UNAVAILABLE:
                    raise LLMRequestError(kind, status, type(e).__name__) from None
                failures.append({"model": model, "http_status": status})
                if i + 1 < len(self.models) and self.notify:
                    self.notify(USER_FALLBACK_MSG)
                continue
            self._record(model, None, None, i > 0, "ok")
            return result
        raise AIServiceUnavailable(failures)

    def _complete(self, model, prompt):
        resp = self._client.chat.completions.create(model=model, temperature=0,
                                                    messages=[{"role": "user", "content": prompt}])
        return resp.choices[0].message.content or ""

    def generate_structured(self, prompt: str, schema):
        instruction = (prompt + "\n\nReturn ONLY one JSON object (no markdown fences, no commentary) that conforms to this JSON Schema:\n"
                       + json.dumps(schema.model_json_schema()))
        return self._with_fallback(lambda model: schema.model_validate(extract_json(self._complete(model, instruction))))

    def generate_text(self, prompt: str) -> str:
        return self._with_fallback(lambda model: self._complete(model, prompt))
