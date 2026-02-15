import base64
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

from .base import Tool, ToolResult


class ScreenTool(Tool):
    def __init__(self, save_dir: Optional[Path] = None):
        self.save_dir = save_dir or Path.home() / ".agentic_cli" / "screenshots"
        self.save_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "screen"

    @property
    def description(self) -> str:
        return "Capture screenshots and get screen information. Useful for visual feedback and understanding the current desktop state."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["capture", "info"],
                    "description": "The screen operation to perform",
                },
                "path": {
                    "type": "string",
                    "description": "Optional path to save screenshot (for capture)",
                },
            },
            "required": ["operation"],
        }

    def _capture_screenshot(self, save_path: Optional[str] = None) -> str:
        system = platform.system()

        if save_path is None:
            save_path = str(self.save_dir / f"screenshot_{int(os.times().elapsed * 1000)}.png")

        try:
            if system == "Darwin":
                subprocess.run(
                    ["screencapture", "-x", save_path],
                    check=True,
                    capture_output=True,
                )
            elif system == "Linux":
                subprocess.run(
                    ["gnome-screenshot", "-f", save_path],
                    check=True,
                    capture_output=True,
                )
            else:
                return ""

            return save_path
        except Exception:
            return ""

    def _get_screen_info(self) -> dict:
        system = platform.system()

        if system == "Darwin":
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return {"info": result.stdout, "system": "macOS"}
            except Exception as e:
                return {"error": str(e), "system": "macOS"}
        elif system == "Linux":
            try:
                result = subprocess.run(
                    ["xrandr"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return {"info": result.stdout, "system": "Linux"}
            except Exception as e:
                return {"error": str(e), "system": "Linux"}

        return {"system": system, "message": "Screen info not available"}

    def execute(
        self,
        operation: str,
        path: Optional[str] = None,
    ) -> ToolResult:
        try:
            if operation == "capture":
                save_path = self._capture_screenshot(path)
                if save_path:
                    with open(save_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    return ToolResult(
                        success=True,
                        result=f"Screenshot saved to {save_path} (base64 length: {len(b64)})",
                    )
                return ToolResult(success=False, result=None, error="Failed to capture screenshot")

            elif operation == "info":
                return ToolResult(success=True, result=self._get_screen_info())

            return ToolResult(success=False, result=None, error="Unknown operation")

        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
