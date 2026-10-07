import re
from backend.agent import prompts
from backend.models.schemas import CodeResponse, PlanAndCode


def strip_fences(code: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", code, re.S)
    return (m.group(1) if m else code).strip() + "\n"


def plan_and_code_prompt(question: str, schema_text: str) -> str:
    return prompts.PLAN_AND_CODE_PROMPT.format(schema=schema_text, question=question)


def repair_prompt(question, plan, schema_text, previous_code, error) -> str:
    return prompts.REPAIR_PROMPT.format(schema=schema_text, question=question, operations="; ".join(plan.operations),
                                        code=previous_code, error=error)


def clean_plan_and_code(pc: PlanAndCode) -> PlanAndCode:
    pc.code = strip_fences(pc.code) if pc.code.strip() else ""
    return pc


def clean_repair(r: CodeResponse) -> str:
    return strip_fences(r.code)
