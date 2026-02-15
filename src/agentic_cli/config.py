import os
from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://home-base:11434"
    model: str = "qwen3:30b-a3b"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_key: Optional[str] = None


class ToolConfig(BaseModel):
    allowed_commands: Optional[list[str]] = None
    forbidden_commands: list[str] = ["rm -rf /", ":(){:|:&};:", "mkfs"]
    shell_timeout: int = 30
    file_allow_list: Optional[list[str]] = None
    file_deny_list: list[str] = []


def path_serializer(dumper, data):
    return dumper.represent_str(str(data))


yaml.add_representer(Path, path_serializer)


class Config(BaseSettings):
    llm: LLMConfig = LLMConfig()
    tools: ToolConfig = ToolConfig()
    history_file: Path = Path.home() / ".agentic_cli_history"

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        if config_path is None:
            config_path = Path.home() / ".agentic_cli" / "config.yaml"

        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}

            if "history_file" in data and isinstance(data["history_file"], str):
                data["history_file"] = Path(data["history_file"])

            return cls(**data)
        return cls()

    def save(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path.home() / ".agentic_cli" / "config.yaml"

        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump()
        if "history_file" in data and isinstance(data["history_file"], Path):
            data["history_file"] = str(data["history_file"])

        with open(config_path, "w") as f:
            yaml.dump(data, f)
