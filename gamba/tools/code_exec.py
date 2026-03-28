"""Python code execution tool - runs code in sandbox."""

from __future__ import annotations

from typing import Any

from gamba.tools.base import BaseTool
from gamba.core.sandbox import execute


class CodeExecTool(BaseTool):
    name = "code_exec"
    description = "Execute Python code and return the output. Set 'result' variable for return value."
    inputs = {"code": "Python code to execute"}
    output_type = "string"

    def forward(self, code: str, **kwargs: Any) -> str:
        exec_result = execute(code, {})
        if exec_result.success:
            parts = []
            if exec_result.output:
                parts.append(exec_result.output)
            if exec_result.result is not None:
                parts.append(f"Result: {exec_result.result}")
            return "\n".join(parts) or "(executed successfully, no output)"
        return f"Error: {exec_result.error}"
