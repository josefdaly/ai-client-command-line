import json
from typing import Optional, Callable
from pydantic import BaseModel

from agentic_cli.llm.client import LLMClient, Message, ChatResponse, ToolCall
from agentic_cli.tools.base import Tool, ToolResult


class Agent:
    def __init__(
        self,
        llm_client: LLMClient,
        tools: list[Tool],
        system_prompt: Optional[str] = None,
        status_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.llm = llm_client
        self.tools = {t.name: t for t in tools}
        self.messages: list[Message] = []
        self.status_callback = status_callback
        self.total_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if system_prompt:
            self.messages.append(Message(role="system", content=system_prompt))
        else:
            self.messages.append(Message(role="system", content=self._default_system_prompt()))

    def _emit_status(self, status: str, message: str):
        if self.status_callback:
            self.status_callback(status, message)

    def _default_system_prompt(self) -> str:
        return """You are a helpful assistant that can control a computer through semantic commands.
        
Available tools:
- shell: Execute shell commands
- files: Read, write, list, and manage files
- screen: Capture screenshots and get screen info

Be concise and efficient. When asked to perform a task, use the appropriate tools to accomplish it.
Always confirm when a task is complete."""

    def reset(self):
        system_msg = self.messages[0] if self.messages else Message(role="system", content="")
        self.messages = [system_msg]

    def chat(self, user_input: str) -> tuple[str, dict]:
        self.messages.append(Message(role="user", content=user_input))

        response = self._execute_loop()

        self.messages.append(Message(role="assistant", content=response.content))

        if response.usage:
            self.total_usage["prompt_tokens"] += response.usage.get("prompt_tokens", 0)
            self.total_usage["completion_tokens"] += response.usage.get("completion_tokens", 0)
            self.total_usage["total_tokens"] += response.usage.get("total_tokens", 0)

        return response.content, self.total_usage

    def _execute_loop(self, max_iterations: int = 10) -> ChatResponse:
        response: Optional[ChatResponse] = None
        for iteration in range(max_iterations):
            tools_schema = [t.to_openai_schema() for t in self.tools.values()]

            self._emit_status("thinking", f"Thinking... (step {iteration + 1})")
            response = self.llm.chat(self.messages, tools=tools_schema)

            if not response.tool_calls:
                return response

            for tc in response.tool_calls:
                tool = self.tools.get(tc.name)
                if not tool:
                    error_msg = f"Tool {tc.name} not found"
                    self.messages.append(
                        Message(
                            role="tool",
                            content=error_msg,
                            tool_call_id=tc.id,
                        )
                    )
                    continue

                self._emit_status("using_tool", f"Running {tc.name}...")
                args = tc.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                result = tool.execute(**args)
                self._emit_status("tool_complete", f"{tc.name} finished")

                tool_result_msg = self._format_tool_result(tc.name, tc.id, result)
                self.messages.append(tool_result_msg)

            if not response.tool_calls:
                break

        return response or ChatResponse(content="")

    def _format_tool_result(
        self, tool_name: str, tool_call_id: Optional[str], result: ToolResult
    ) -> Message:
        if result.success:
            content = f"Tool '{tool_name}' result: {result.result}"
        else:
            content = f"Tool '{tool_name}' error: {result.error}"

        return Message(
            role="user",
            content=content,
            tool_call_id=None,
        )

    def get_history(self) -> list[Message]:
        return self.messages
