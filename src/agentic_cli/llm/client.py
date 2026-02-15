from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel
import httpx


class ToolCall(BaseModel):
    id: Optional[str] = None
    name: str
    arguments: dict[str, Any]


class Message(BaseModel):
    role: str
    content: str
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    tool_calls: Optional[list[ToolCall]] = None
    usage: Optional[dict] = None


class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[Message], tools: Optional[list[dict]] = None) -> ChatResponse:
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        pass


class OllamaClient(LLMClient):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Optional[Any] = None

    @property
    def client(self):
        if self._client is None:
            import httpx

            self._client = httpx.Client(base_url=self.base_url, timeout=120.0)
        return self._client

    def chat(self, messages: list[Message], tools: Optional[list[dict]] = None) -> ChatResponse:
        payload = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        response = self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        tool_calls = None
        if data.get("message", {}).get("tool_calls"):
            tool_calls = [
                ToolCall(name=tc["function"]["name"], arguments=tc["function"]["arguments"])
                for tc in data["message"]["tool_calls"]
            ]

        return ChatResponse(
            content=data["message"]["content"],
            tool_calls=tool_calls,
            usage=data.get("usage"),
        )

    def get_available_models(self) -> list[str]:
        response = self.client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]


class OpenCodeClient(LLMClient):
    def __init__(
        self,
        base_url: str = "https://opencode.ai",
        model: str = "big-pickle",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key
        self._client: Optional[Any] = None

    @property
    def client(self):
        if self._client is None:
            import httpx

            self._client = httpx.Client(base_url=self.base_url, timeout=120.0)
        return self._client

    def chat(self, messages: list[Message], tools: Optional[list[dict]] = None) -> ChatResponse:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        data: dict = {"choices": []}
        response = self.client.post("/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        # OpenCode API uses "choices" format like standard Chat Completions
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice:
                content = choice["message"].get("content", "")
                tool_calls = None
                if choice["message"].get("tool_calls"):
                    tool_calls = []
                    for tc in choice["message"]["tool_calls"]:
                        func = tc["function"]
                        args = func.get("arguments")
                        if isinstance(args, str):
                            import json

                            args = json.loads(args)
                        tool_calls.append(
                            ToolCall(id=tc.get("id"), name=func["name"], arguments=args)
                        )
                return ChatResponse(
                    content=content,
                    tool_calls=tool_calls,
                    usage=data.get("usage"),
                )

        return ChatResponse(content=str(data))

    def get_available_models(self) -> list[str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = self.client.get("/api/models", headers=headers)
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]


def get_llm_client(provider: str = "ollama", **kwargs) -> LLMClient:
    if provider == "ollama":
        return OllamaClient(**kwargs)
    if provider == "opencode":
        return OpenCodeClient(**kwargs)
    raise ValueError(f"Unknown provider: {provider}")
