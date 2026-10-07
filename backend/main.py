"""CLI for quick debugging without the UI:
   python -m backend.main "Which product has the highest profit?" data/sample/*.csv data/sample/*.xlsx"""
import sys
from backend.agent.agent import DataAnalystAgent
from backend.ingestion import load_many
from backend.llm.openrouter import OpenRouterClient


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    skipped: list[str] = []
    tables = load_many(argv[2:], skipped)
    for m in skipped:
        print(f"[skipped] {m}")
    r = DataAnalystAgent(OpenRouterClient()).analyze(argv[1], tables, progress=lambda s: print(f"[{s}]"))
    print(f"\nSTATUS: {r.status.value}\nANSWER: {r.answer}\nREASON: {r.reason}\n\nCODE:\n{r.code}\nSTRUCTURED RESULT:\n"
          f"{r.structured_result.model_dump_json(exclude_none=True) if r.structured_result else (r.execution.stdout if r.execution else '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
