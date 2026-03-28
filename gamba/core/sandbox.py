"""Code execution sandbox for SmolAgents-style tool calling.

Agents write Python code that calls tools as functions. This module
executes that code in a restricted environment.
"""

from __future__ import annotations

import io
import contextlib
from dataclasses import dataclass
from typing import Any

SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "format": format,
    "frozenset": frozenset, "int": int, "isinstance": isinstance,
    "issubclass": issubclass, "len": len, "list": list, "map": map,
    "max": max, "min": min, "print": print, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
    "zip": zip, "True": True, "False": False, "None": None,
}

ALLOWED_IMPORTS = {
    "json", "math", "re", "datetime", "collections", "itertools",
    "functools", "pathlib", "os.path", "urllib.parse", "textwrap",
}


@dataclass
class ExecutionResult:
    success: bool
    output: str = ""
    result: Any = None
    error: str = ""


def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
    if name not in ALLOWED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed. Allowed: {ALLOWED_IMPORTS}")
    return __builtins__["__import__"](name, *args, **kwargs) if isinstance(__builtins__, dict) else __import__(name, *args, **kwargs)


def execute(code: str, tools: dict[str, Any]) -> ExecutionResult:
    """Execute agent-generated Python code with tools available as callables."""
    namespace: dict[str, Any] = {}
    namespace.update({name: tool for name, tool in tools.items()})
    namespace["__builtins__"] = {**SAFE_BUILTINS, "__import__": _safe_import}
    namespace["result"] = None

    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exec(code, namespace)
        return ExecutionResult(
            success=True,
            output=stdout.getvalue(),
            result=namespace.get("result"),
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            output=stdout.getvalue(),
            error=f"{type(e).__name__}: {e}",
        )
