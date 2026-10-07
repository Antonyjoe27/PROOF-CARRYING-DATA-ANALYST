"""Runs validated generated code in a separate, restricted Python subprocess.

Layers: (1) static AST validation (sandbox.py), (2) isolated subprocess (`-I`, temp cwd, empty environment, CPU and
file-size limits, wall-clock timeout), (3) inside the child: restricted builtins (no open/eval/exec), a whitelisting
`__import__`, and blocked sockets. A controlled hackathon environment, not a hardened production sandbox.
"""
import os
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

from backend.models.schemas import ExecutionResult
from .sandbox import ALLOWED_IMPORTS, validate_code

MAX_OUT = 20_000

RUNNER = '''import builtins as _b, pickle as _pk, sys as _sys, socket as _s
def _blocked(*a, **k):
    raise RuntimeError("network access is disabled")
for _n in ("socket", "create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "socketpair"):
    setattr(_s, _n, _blocked)
import pandas as pd, numpy as np, json, math
_ALLOWED = set(__ALLOWED__)
_real_import = _b.__import__
def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0 or name.split(".")[0] not in _ALLOWED:
        raise ImportError("import of '%s' is not allowed" % name)
    return _real_import(name, globals, locals, fromlist, level)
_SAFE = {n: getattr(_b, n) for n in (
    "abs all any bool bytes callable chr dict divmod enumerate filter float format frozenset int isinstance "
    "iter len list map max min next ord pow print range repr reversed round set slice sorted str sum tuple zip "
    "Exception ArithmeticError AssertionError AttributeError IndexError KeyError LookupError NameError "
    "NotImplementedError OverflowError RuntimeError StopIteration TypeError ValueError ZeroDivisionError "
    "True False None").split() if hasattr(_b, n)}
_SAFE["__import__"] = _safe_import
_env = dict(_pk.load(open(_sys.argv[1], "rb")))
_env.update(pd=pd, np=np, json=json, math=math)
_env["__builtins__"] = _SAFE
_src = open(_sys.argv[2], encoding="utf-8").read()
exec(compile(_src, "generated_code.py", "exec"), _env)
'''


def build_child_env() -> dict:
    """Environment for the child process: nothing inherited from the parent (so no API keys / .env values)."""
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    return env


def _limits():  # runs in the child before exec (posix only)
    try:
        import resource
        import signal
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))      # generated code cannot write files
    except Exception:
        pass


def execute_code(code: str, dataframes: dict, timeout: int = 30, _skip_static_validation: bool = False) -> ExecutionResult:
    """`_skip_static_validation` exists ONLY so tests can prove the runtime layers hold on their own."""
    if not _skip_static_validation:
        problems = validate_code(code)
        if problems:
            return ExecutionResult(success=False, stderr="Blocked by sandbox: " + "; ".join(problems),
                                   blocked_reasons=problems)
    with tempfile.TemporaryDirectory() as tmp:
        data_path, code_path, runner_path = (Path(tmp) / n for n in ("data.pkl", "generated_code.py", "runner.py"))
        with open(data_path, "wb") as f:
            pickle.dump(dataframes, f)
        code_path.write_text(code, encoding="utf-8")
        runner_path.write_text(RUNNER.replace("__ALLOWED__", repr(sorted(ALLOWED_IMPORTS))), encoding="utf-8")
        try:
            p = subprocess.run([sys.executable, "-I", "-B", str(runner_path), str(data_path), str(code_path)], cwd=tmp,
                               env=build_child_env(), capture_output=True, text=True, timeout=timeout,
                               preexec_fn=_limits if os.name == "posix" else None)
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else ""
            return ExecutionResult(success=False, stdout=out[:MAX_OUT], stderr=f"Timed out after {timeout}s", timed_out=True)
    return ExecutionResult(success=p.returncode == 0, stdout=p.stdout[:MAX_OUT], stderr=p.stderr[-4000:], returncode=p.returncode)
