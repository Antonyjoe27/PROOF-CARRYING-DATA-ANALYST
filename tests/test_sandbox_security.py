"""Attempts to escape the controlled execution environment. Static validation AND the runtime layers are tested."""
import os
import pandas as pd
import pytest
from backend.execution.executor import build_child_env, execute_code
from backend.execution.sandbox import ALLOWED_IMPORTS, validate_code

DF = {"t_df": pd.DataFrame({"a": [1, 2, 3]})}

ATTACKS = {
    "read secrets/.env": ["open('.env').read()", "pd.read_csv('.env')", "pd.read_table('/etc/passwd')"],
    "environment variables": ["import os\nprint(os.environ)", "import os\nos.getenv('OPENROUTER_API_KEY')", "pd.io.common.os.environ",
                              "from os import environ"],
    "arbitrary file access": ["open('/etc/passwd')", "pd.read_excel('x.xlsx')", "np.load('x.npy')", "np.loadtxt('x')",
                              "pd.ExcelFile('x.xlsx')", "import pathlib"],
    "file writes / modifying sources": ["t_df.to_csv('x.csv')", "t_df.to_excel('x.xlsx')", "t_df.to_pickle('x')",
                                        "np.save('x', t_df.a.values)", "import shutil\nshutil.rmtree('data')"],
    "network": ["import socket", "import urllib.request", "import requests", "import http.client",
                "pd.read_csv('http://example.com/x.csv')"],
    "subprocess / shell": ["import subprocess", "import os\nos.system('ls')", "pd.io.common.os.system('ls')",
                           "import pty", "__import__('subprocess')"],
    "dynamic code / reflection": ["eval('1+1')", "exec('x=1')", "compile('1','a','eval')", "getattr(pd, 'x')",
                                  "t_df.__class__.__bases__", "'{0.__class__}'.format(t_df)", "globals()", "type(t_df)"],
    "package install / arbitrary imports": ["import pip", "import ensurepip", "import importlib", "import sys"],
    "duckdb removed": ["import duckdb", "from duckdb import sql"],
}


@pytest.mark.parametrize("kind,code", [(k, c) for k, v in ATTACKS.items() for c in v])
def test_static_validation_blocks(kind, code):
    assert validate_code(code), f"{kind}: not blocked: {code!r}"
    r = execute_code(code, DF)
    assert not r.success and r.blocked_reasons, f"{kind}: executed {code!r}"


def test_duckdb_not_in_allowlist():
    assert "duckdb" not in ALLOWED_IMPORTS and ALLOWED_IMPORTS >= {"pandas", "numpy", "json", "math"}


def test_safe_code_still_runs():
    r = execute_code("import numpy as np\nfrom collections import Counter\nprint(json.dumps({'s': int(t_df.a.sum()), 'm': math.sqrt(4)}))", DF)
    assert r.success and '"s": 6' in r.stdout


# ---- runtime layers hold even if static validation were bypassed (test-only flag) ----
@pytest.mark.parametrize("code,needle", [
    ("open('/etc/passwd')", "name 'open' is not defined"),
    ("import os", "not allowed"), ("import subprocess", "not allowed"), ("import socket", "not allowed"),
    ("__import__('os')", "not allowed"), ("import duckdb", "not allowed"),
    ("eval('1')", "name 'eval' is not defined"),
])
def test_runtime_layer_blocks_without_static_validation(code, needle):
    r = execute_code(code, DF, _skip_static_validation=True)
    assert not r.success and needle in r.stderr


def test_child_env_has_no_secrets(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "SECRET123")
    env = build_child_env()
    assert "OPENROUTER_API_KEY" not in env and "SECRET123" not in "".join(env.values())


def test_generated_code_cannot_modify_source_data():
    before = DF["t_df"].copy()
    r = execute_code("t_df['a'] = 0\nprint(t_df.a.sum())", DF)
    assert r.success and r.stdout.strip() == "0"
    pd.testing.assert_frame_equal(DF["t_df"], before)   # parent copy untouched


def test_file_write_impossible_even_if_reachable():
    r = execute_code("t_df.to_csv('x.csv')", DF)
    assert not r.success


def test_timeout_and_failure_reporting():
    assert execute_code("while True:\n    pass", DF, timeout=2).timed_out
    r = execute_code("print(1/0)", DF)
    assert not r.success and r.returncode != 0 and "ZeroDivisionError" in r.stderr
