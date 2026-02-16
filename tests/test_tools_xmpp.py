import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from agentic_cli.tools.xmpp import XMPPTool
from agentic_cli.tools.base import ToolResult


class TestXMPPTool:
    def test_tool_name(self):
        with patch("agentic_cli.tools.xmpp.XMPPService") as mock_service_class:
            mock_service = Mock()
            mock_service.initialize.return_value = True
            mock_service.send.return_value = (True, None)
            mock_service_class.return_value = mock_service

            tool = XMPPTool()
            assert tool.name == "xmpp"

    def test_tool_description(self):
        with patch("agentic_cli.tools.xmpp.XMPPService"):
            tool = XMPPTool()
            assert "XMPP" in tool.description
            assert "recipient" in tool.description
            assert "message" in tool.description
            assert "file" in tool.description

    def test_tool_parameters(self):
        with patch("agentic_cli.tools.xmpp.XMPPService"):
            tool = XMPPTool()
            params = tool.parameters

            assert "recipient" in params["properties"]
            assert "message" in params["properties"]
            assert "attachment" in params["properties"]
            assert "recipient" in params["required"]
            assert "message" in params["required"]

    @patch("agentic_cli.tools.xmpp.XMPPService")
    def test_execute_success(self, mock_service_class):
        mock_service = Mock()
        mock_service.initialize.return_value = True
        mock_service.send.return_value = (True, None)
        mock_service_class.return_value = mock_service

        tool = XMPPTool()
        result = tool.execute(recipient="joe@example.com", message="Hello")

        assert result.success is True
        assert "joe@example.com" in result.result

    @patch("agentic_cli.tools.xmpp.XMPPService")
    def test_execute_failure(self, mock_service_class):
        mock_service = Mock()
        mock_service.initialize.return_value = True
        mock_service.send.return_value = (False, "Connection failed")
        mock_service_class.return_value = mock_service

        tool = XMPPTool()
        result = tool.execute(recipient="joe@example.com", message="Hello")

        assert result.success is False
        assert "Connection failed" in result.error

    @patch("agentic_cli.tools.xmpp.XMPPService")
    def test_execute_with_attachment(self, mock_service_class):
        mock_service = Mock()
        mock_service.initialize.return_value = True
        mock_service.send.return_value = (True, None)
        mock_service_class.return_value = mock_service

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Attachment content")
            f.flush()
            temp_path = f.name

        try:
            tool = XMPPTool()
            result = tool.execute(
                recipient="joe@example.com", message="Hello", attachment=temp_path
            )

            assert result.success is True
            assert "attachment" in result.result.lower()

            mock_service.send.assert_called_once()
            call_args = mock_service.send.call_args
            assert call_args[0][0] == "joe@example.com"
            assert call_args[0][1] == "Hello"
            assert call_args[0][2] == "Attachment content"
        finally:
            os.unlink(temp_path)

    @patch("agentic_cli.tools.xmpp.XMPPService")
    def test_execute_attachment_not_found(self, mock_service_class):
        mock_service = Mock()
        mock_service.initialize.return_value = True
        mock_service.send.return_value = (True, None)
        mock_service_class.return_value = mock_service

        tool = XMPPTool()
        result = tool.execute(
            recipient="joe@example.com", message="Hello", attachment="/nonexistent/file.txt"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @patch("agentic_cli.tools.xmpp.XMPPService")
    def test_execute_service_exception(self, mock_service_class):
        mock_service = Mock()
        mock_service.initialize.return_value = True
        mock_service.send.side_effect = Exception("Connection failed")
        mock_service_class.return_value = mock_service

        tool = XMPPTool()
        result = tool.execute(recipient="joe@example.com", message="Hello")

        assert result.success is False
        assert "Connection failed" in result.error
