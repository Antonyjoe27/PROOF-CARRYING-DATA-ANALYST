import re

_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def years_in_question(question: str) -> list[int]:
    return sorted({int(y) for y in _YEAR.findall(question)})
