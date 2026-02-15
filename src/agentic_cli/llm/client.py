from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel


class ToolCall(BaseModel):
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

        return ChatResponse(content=data["message"]["content"], tool_calls=tool_calls)

    def get_available_models(self) -> list[str]:
        response = self.client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]


def get_llm_client(provider: str = "ollama", **kwargs) -> LLMClient:
    if provider == "ollama":
        return OllamaClient(**kwargs)
    raise ValueError(f"Unknown provider: {provider}")
