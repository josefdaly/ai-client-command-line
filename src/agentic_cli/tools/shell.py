import subprocess
import shlex
from typing import Optional

from .base import Tool, ToolResult


class ShellTool(Tool):
    def __init__(
        self,
        allowed_commands: Optional[list[str]] = None,
        forbidden_commands: list[str] = None,
        timeout: int = 30,
    ):
        self.allowed_commands = allowed_commands
        self.forbidden_commands = forbidden_commands or [
            "rm -rf /",
            ":(){:|:&};:",
            "mkfs",
            "> /dev/sda",
            "dd if=/dev/zero of=",
        ]
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use for running programs, file operations, system info, and any command-line tasks."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
            },
            "required": ["command"],
        }

    def _is_command_safe(self, command: str) -> bool:
        cmd_lower = command.lower().strip()

        if self.allowed_commands:
            for allowed in self.allowed_commands:
                if cmd_lower.startswith(allowed.lower()):
                    return True
            return False

        for forbidden in self.forbidden_commands:
            if forbidden.lower() in cmd_lower:
                return False

        return True

    def execute(self, command: str) -> ToolResult:
        if not self._is_command_safe(command):
            return ToolResult(success=False, result=None, error="Command is not allowed")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            output = result.stdout
            if result.stderr:
                output += f"\nStderr: {result.stderr}"

            return ToolResult(
                success=result.returncode == 0,
                result=output or f"Command completed with exit code {result.returncode}",
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, result=None, error=f"Command timed out after {self.timeout} seconds"
            )
        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
