"""Shell command execution tool."""

from __future__ import annotations

import subprocess
from typing import Any

from gamba.tools.base import BaseTool


class ShellTool(BaseTool):
    name = "shell"
    description = "Execute a shell command and return stdout + stderr. Timeout: 60 seconds."
    inputs = {"command": "Shell command to execute"}
    output_type = "string"

    def forward(self, command: str, **kwargs: Any) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr] {result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 60 seconds"
        except Exception as e:
            return f"Error: {e}"
