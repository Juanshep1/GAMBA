"""File I/O tools - read, write, list files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gamba.tools.base import BaseTool


class FileReadTool(BaseTool):
    name = "file_read"
    description = "Read the contents of a file."
    inputs = {"path": "File path to read"}
    output_type = "string"

    def forward(self, path: str, **kwargs: Any) -> str:
        p = Path(path)
        if not p.exists():
            return f"Error: File not found: {path}"
        if not p.is_file():
            return f"Error: Not a file: {path}"
        try:
            return p.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Write content to a file. Creates parent directories if needed."
    inputs = {"path": "File path to write", "content": "Content to write"}
    output_type = "string"

    def forward(self, path: str, content: str, **kwargs: Any) -> str:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing file: {e}"


class FileListTool(BaseTool):
    name = "file_list"
    description = "List files and directories in a path."
    inputs = {"path": "Directory path to list (default: current dir)"}
    output_type = "string"

    def forward(self, path: str = ".", **kwargs: Any) -> str:
        p = Path(path)
        if not p.exists():
            return f"Error: Path not found: {path}"
        if not p.is_dir():
            return f"Error: Not a directory: {path}"
        entries = []
        for item in sorted(p.iterdir()):
            prefix = "[DIR]" if item.is_dir() else "[FILE]"
            entries.append(f"  {prefix} {item.name}")
        return "\n".join(entries) if entries else "(empty directory)"
