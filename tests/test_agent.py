import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAgent:
    def test_agent_initialization(self):
        from agentic_cli.agent import Agent
        from agentic_cli.llm.client import OllamaClient
        from agentic_cli.tools import ShellTool, FileTool, ScreenTool

        mock_llm = Mock(spec=OllamaClient)
        mock_llm.chat.return_value = Mock(content="Hello", tool_calls=None)

        tools = [ShellTool(), FileTool(), ScreenTool()]

        agent = Agent(mock_llm, tools)

        assert len(agent.tools) == 3
        assert "shell" in agent.tools
        assert "files" in agent.tools
        assert "screen" in agent.tools

    def test_agent_chat(self):
        from agentic_cli.agent import Agent
        from agentic_cli.llm.client import OllamaClient, ChatResponse
        from agentic_cli.tools import ShellTool

        mock_llm = Mock(spec=OllamaClient)
        mock_llm.chat.return_value = ChatResponse(content="Response!", tool_calls=None)

        tools = [ShellTool()]
        agent = Agent(mock_llm, tools)

        response = agent.chat("Hello")

        assert response == "Response!"
        assert len(agent.messages) == 3  # system + user + assistant

    def test_agent_reset(self):
        from agentic_cli.agent import Agent
        from agentic_cli.llm.client import OllamaClient, ChatResponse
        from agentic_cli.tools import ShellTool

        mock_llm = Mock(spec=OllamaClient)
        mock_llm.chat.return_value = ChatResponse(content="Response!", tool_calls=None)

        tools = [ShellTool()]
        agent = Agent(mock_llm, tools)

        agent.chat("Hello")
        assert len(agent.messages) > 1

        agent.reset()
        assert len(agent.messages) == 1  # Only system message remains
