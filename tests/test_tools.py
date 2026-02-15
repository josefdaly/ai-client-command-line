import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from agentic_cli.tools.shell import ShellTool
from agentic_cli.tools.files import FileTool
from agentic_cli.tools.screen import ScreenTool
from agentic_cli.tools.base import ToolResult


class TestShellTool:
    def test_execute_basic_command(self):
        tool = ShellTool()
        result = tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.result

    def test_execute_forbidden_command(self):
        tool = ShellTool()
        result = tool.execute(command="rm -rf /")
        assert result.success is False
        assert "not allowed" in result.error.lower()

    def test_command_timeout(self):
        tool = ShellTool(timeout=1)
        result = tool.execute(command="sleep 10")
        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_invalid_command(self):
        tool = ShellTool()
        result = tool.execute(command="nonexistent_command_xyz")
        assert result.success is False

    def test_allowed_commands_whitelist(self):
        tool = ShellTool(allowed_commands=["git"])
        result = tool.execute(command="git status")
        assert result.success is True

    def test_allowed_commands_blocked(self):
        tool = ShellTool(allowed_commands=["git"])
        result = tool.execute(command="ls")
        assert result.success is False


class TestFileTool:
    def test_read_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        tool = FileTool(allow_list=[str(tmp_path)])
        result = tool.execute(operation="read", path=str(test_file))

        assert result.success is True
        assert result.result == "hello world"

    def test_write_file(self, tmp_path):
        tool = FileTool(allow_list=[str(tmp_path)])
        result = tool.execute(
            operation="write", path=str(tmp_path / "new.txt"), content="new content"
        )

        assert result.success is True
        assert (tmp_path / "new.txt").read_text() == "new content"

    def test_list_directory(self, tmp_path):
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()

        tool = FileTool(allow_list=[str(tmp_path)])
        result = tool.execute(operation="list", path=str(tmp_path))

        assert result.success is True
        assert "file1.txt" in result.result

    def test_file_exists(self, tmp_path):
        test_file = tmp_path / "exists.txt"
        test_file.write_text("test")

        tool = FileTool(allow_list=[str(tmp_path)])
        result = tool.execute(operation="exists", path=str(test_file))

        assert result.success is True
        assert result.result is True

    def test_file_not_found(self, tmp_path):
        tool = FileTool(allow_list=[str(tmp_path)])
        result = tool.execute(operation="read", path=str(tmp_path / "nonexistent.txt"))

        assert result.success is False

    def test_search_files(self, tmp_path):
        (tmp_path / "test.py").touch()
        (tmp_path / "test.txt").touch()
        (tmp_path / "other.txt").touch()

        tool = FileTool(allow_list=[str(tmp_path)])
        result = tool.execute(operation="search", path=str(tmp_path), pattern="test.*")

        assert result.success is True
        assert "test.py" in result.result
        assert "test.txt" in result.result

    def test_path_not_allowed(self, tmp_path):
        tool = FileTool(allow_list=[str(tmp_path)])
        result = tool.execute(operation="read", path="/etc/passwd")

        assert result.success is False


class TestScreenTool:
    @patch("agentic_cli.tools.screen.platform.system")
    @patch("agentic_cli.tools.screen.subprocess.run")
    def test_capture_screenshot(self, mock_run, mock_system, tmp_path):
        mock_system.return_value = "Darwin"
        mock_run.return_value = Mock(returncode=0)

        screenshot_path = tmp_path / "test_screenshot.png"

        tool = ScreenTool(save_dir=tmp_path)
        result = tool.execute(operation="capture", path=str(screenshot_path))

        mock_run.assert_called_once()
        assert "screencapture" in mock_run.call_args[0][0]
        assert str(screenshot_path) in mock_run.call_args[0][0]

    def test_screen_info(self):
        tool = ScreenTool()
        result = tool.execute(operation="info")

        assert result.success is True
        assert "system" in result.result

    def test_unknown_operation(self):
        tool = ScreenTool()
        result = tool.execute(operation="unknown")

        assert result.success is False
