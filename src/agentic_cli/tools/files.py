import os
from pathlib import Path
from typing import Optional

from .base import Tool, ToolResult


class FileTool(Tool):
    def __init__(
        self,
        allow_list: Optional[list[str]] = None,
        deny_list: list[str] = None,
    ):
        self.allow_list = allow_list
        self.deny_list = deny_list or []

    @property
    def name(self) -> str:
        return "files"

    @property
    def description(self) -> str:
        return "Read, write, list, and manage files. Use for creating/editing documents, reading code, searching files, and file metadata."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete", "exists", "info", "search"],
                    "description": "The file operation to perform",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write operation)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (for search operation)",
                },
            },
            "required": ["operation", "path"],
        }

    def _is_path_safe(self, path: str) -> bool:
        try:
            resolved = Path(path).resolve()

            if self.allow_list:
                for allowed in self.allow_list:
                    allowed_path = Path(allowed).resolve()
                    if resolved.is_relative_to(allowed_path):
                        return True
                return False

            for denied in self.deny_list:
                denied_path = Path(denied).resolve()
                if resolved.is_relative_to(denied_path):
                    return False

            return True
        except Exception:
            return False

    def execute(
        self,
        operation: str,
        path: str,
        content: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> ToolResult:
        if not self._is_path_safe(path):
            return ToolResult(success=False, result=None, error="Path is not allowed")

        try:
            p = Path(path)

            if operation == "read":
                if not p.exists():
                    return ToolResult(success=False, result=None, error="File not found")
                if p.is_dir():
                    return ToolResult(success=False, result=None, error="Path is a directory")
                return ToolResult(success=True, result=p.read_text())

            elif operation == "write":
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content or "")
                return ToolResult(success=True, result=f"Written to {path}")

            elif operation == "list":
                if not p.exists():
                    return ToolResult(success=False, result=None, error="Directory not found")
                items = []
                for item in p.iterdir():
                    items.append(f"{'d' if item.is_dir() else '-'} {item.name}")
                return ToolResult(success=True, result="\n".join(items))

            elif operation == "delete":
                if not p.exists():
                    return ToolResult(success=False, result=None, error="Path not found")
                if p.is_dir():
                    p.rmdir()
                else:
                    p.unlink()
                return ToolResult(success=True, result=f"Deleted {path}")

            elif operation == "exists":
                return ToolResult(success=True, result=p.exists())

            elif operation == "info":
                if not p.exists():
                    return ToolResult(success=False, result=None, error="Path not found")
                stat = p.stat()
                return ToolResult(
                    success=True,
                    result={
                        "size": stat.st_size,
                        "is_file": p.is_file(),
                        "is_dir": p.is_dir(),
                        "modified": stat.st_mtime,
                    },
                )

            elif operation == "search":
                if pattern is None:
                    return ToolResult(
                        success=False, result=None, error="Pattern required for search"
                    )
                results = []
                for match in p.rglob(pattern):
                    results.append(str(match))
                return ToolResult(
                    success=True, result="\n".join(results) if results else "No matches found"
                )

            return ToolResult(success=False, result=None, error="Unknown operation")

        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
