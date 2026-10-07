import json
from backend.models.schemas import AnswerClaim, StructuredResult
from backend.verification.verifier import format_value
from . import prompts


def explain_prompt(question: str, result: StructuredResult, feedback: str = "") -> str:
    fb = f"\nYour previous explanation was rejected: {feedback}\nFix it.\n" if feedback else ""
    return prompts.EXPLAIN_PROMPT.format(question=question, feedback=fb,
                                         result=json.dumps(result.model_dump(exclude_none=True), default=str))


def render_answer(r: StructuredResult) -> str:
    """THE final answer. Built by the application ONLY from the verified structured result: entity, value, unit,
    operation/direction and comparison values are injected here; LLM's wording can never replace them."""
    v = format_value(r.value, r.unit)
    if r.result_type == "ranking":
        return f"{r.selected_entity} had the {r.direction} {r.metric}: {v}."
    if r.result_type == "aggregate":
        return f"The {r.operation} of {r.metric} was {v}."
    return f"Comparison of {r.metric}: " + "; ".join(f"{k} = {format_value(x, r.unit)}" for k, x in (r.values or {}).items()) + "."
