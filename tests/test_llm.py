import pytest
from unittest.mock import Mock, patch, MagicMock

from agentic_cli.llm.client import OllamaClient, Message, ChatResponse, ToolCall


class TestOllamaClient:
    @patch("httpx.Client")
    def test_chat_basic(self, mock_client_class):
        mock_response = Mock()
        mock_response.json.return_value = {"message": {"content": "Hello!"}}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = OllamaClient(base_url="http://localhost:11434", model="llama3.2")
        messages = [Message(role="user", content="Hi")]

        response = client.chat(messages)

        assert response.content == "Hello!"
        assert response.tool_calls is None

    @patch("httpx.Client")
    def test_chat_with_tools(self, mock_client_class):
        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "shell", "arguments": {"command": "echo test"}}}
                ],
            }
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = OllamaClient()
        messages = [Message(role="user", content="Run echo")]

        tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": "Run shell commands",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            }
        ]

        response = client.chat(messages, tools=tools_schema)

        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "shell"

    @patch("httpx.Client")
    def test_get_available_models(self, mock_client_class):
        mock_response = Mock()
        mock_response.json.return_value = {"models": [{"name": "llama3.2"}, {"name": "codellama"}]}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = OllamaClient()
        models = client.get_available_models()

        assert "llama3.2" in models
        assert "codellama" in models


class TestMessage:
    def test_message_creation(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_with_tool_calls(self):
        tc = ToolCall(name="shell", arguments={"command": "ls"})
        msg = Message(role="assistant", content="", tool_calls=[tc])

        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "shell"
