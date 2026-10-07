"""Static validation of generated code BEFORE it is allowed to run.

This is one layer of a *controlled hackathon execution environment* (static checks + restricted builtins +
isolated subprocess with stripped env, timeout, blocked sockets). It is NOT a production-grade security sandbox.
"""
import ast

# pandas + numpy + a few side-effect-free standard-library modules. DuckDB is intentionally NOT allowed (it can
# read/write arbitrary files and attach external sources).
ALLOWED_IMPORTS = frozenset({"pandas", "numpy", "math", "json", "datetime", "re", "statistics", "decimal", "collections"})

FORBIDDEN_CALLS = frozenset({
    "open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "vars", "dir", "help", "type",
    "getattr", "setattr", "delattr", "hasattr", "breakpoint", "exit", "quit", "memoryview", "object", "super"})

# attribute names that reach files, processes, the network, the OS or module internals
FORBIDDEN_ATTRS = frozenset({
    "to_csv", "to_excel", "to_pickle", "to_parquet", "to_feather", "to_hdf", "to_sql", "to_stata", "to_orc", "to_xml",
    "to_clipboard", "to_latex", "to_html", "ExcelFile", "ExcelWriter", "HDFStore", "read_pickle",
    "load", "save", "savez", "savez_compressed", "savetxt", "loadtxt", "genfromtxt", "fromfile", "tofile",
    "fromregex", "memmap", "lib", "ctypeslib", "testing", "f2py",
    "system", "popen", "spawn", "fork", "exec_module", "remove", "unlink", "rmdir", "rmtree", "mkdir",
    "makedirs", "listdir", "walk", "chmod", "environ", "getenv", "putenv", "urlopen", "urlretrieve",
    "os", "sys", "io", "subprocess", "socket", "shutil", "pathlib", "builtins", "importlib", "ctypes", "pickle",
    "requests", "urllib", "http", "ftplib", "smtplib", "compat", "util", "_libs", "core", "__dict__"})

FORBIDDEN_NAMES = frozenset({"os", "sys", "subprocess", "socket", "shutil", "pathlib", "builtins", "importlib",
                             "ctypes", "pickle", "requests", "urllib", "duckdb"})


def validate_code(code: str) -> list[str]:
    """Return a list of violations; an empty list means the code may run."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]
    errs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    errs.append(f"Import not allowed: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                errs.append(f"Import not allowed: {'.' * node.level}{node.module or ''}")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in FORBIDDEN_CALLS:
                errs.append(f"Call not allowed: {f.id}()")
            if isinstance(f, ast.Attribute) and f.attr.startswith("read_"):
                errs.append(f"File/network reader not allowed: .{f.attr}()")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                errs.append(f"Dunder attribute not allowed: {node.attr}")
            elif node.attr in FORBIDDEN_ATTRS:
                errs.append(f"Attribute not allowed: .{node.attr}")
        elif isinstance(node, ast.Name):
            if node.id.startswith("_") or node.id in FORBIDDEN_NAMES:
                errs.append(f"Name not allowed: {node.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
            errs.append("String containing '__' not allowed (format-string attribute tricks)")
        elif isinstance(node, (ast.ClassDef, ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await)):
            errs.append(f"Statement not allowed: {type(node).__name__}")
    return sorted(set(errs))
