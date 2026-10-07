import pandas as pd
import pytest
from backend.execution.executor import execute_code
from backend.execution.sandbox import validate_code

DF = {"t_df": pd.DataFrame({"a": [1, 2, 3], "g": ["x", "x", "y"]})}


def test_runs_and_captures_stdout():
    r = execute_code("print(t_df.a.sum())", DF)
    assert r.success and r.stdout.strip() == "6"


@pytest.mark.parametrize("code", ["import os", "import subprocess", "open('x')", "eval('1')", "__import__('os')",
                                  "t_df.to_csv('x.csv')", "import socket", "pd.read_csv('x')", "t_df.__class__"])
def test_dangerous_code_blocked(code):
    assert validate_code(code)
    assert not execute_code(code, DF).success


def test_runtime_failure_reported():
    r = execute_code("print(1/0)", DF)
    assert not r.success and "ZeroDivisionError" in r.stderr


def test_timeout():
    r = execute_code("while True:\n    pass", DF, timeout=2)
    assert r.timed_out and not r.success


def test_secrets_not_visible(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "SECRET123")
    r = execute_code("print('ok')", DF)
    assert "SECRET123" not in r.stdout + r.stderr
