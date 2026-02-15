import pytest
import tempfile
import yaml
from pathlib import Path

from agentic_cli.config import Config, LLMConfig, ToolConfig


class TestConfig:
    def test_default_config(self):
        config = Config()

        assert config.llm.provider == "ollama"
        assert config.llm.model == "llama3.2"
        assert config.tools.shell_timeout == 30
        assert len(config.tools.forbidden_commands) > 0

    def test_config_with_values(self):
        config = Config(
            llm=LLMConfig(provider="ollama", model="codellama"), tools=ToolConfig(shell_timeout=60)
        )

        assert config.llm.model == "codellama"
        assert config.tools.shell_timeout == 60

    def test_config_save_load(self):
        config = Config(llm=LLMConfig(model="test-model"), tools=ToolConfig(shell_timeout=45))

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config.save(config_path)

            loaded = Config.load(config_path)

            assert loaded.llm.model == "test-model"
            assert loaded.tools.shell_timeout == 45

    def test_config_load_nonexistent(self):
        config = Config.load(Path("/nonexistent/config.yaml"))

        assert config.llm.provider == "ollama"
        assert config.llm.model == "llama3.2"
