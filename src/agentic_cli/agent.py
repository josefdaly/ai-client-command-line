from typing import Optional
from pydantic import BaseModel

from agentic_cli.llm.client import LLMClient, Message, ChatResponse, ToolCall
from agentic_cli.tools.base import Tool, ToolResult


class Agent:
    def __init__(
        self,
        llm_client: LLMClient,
        tools: list[Tool],
        system_prompt: Optional[str] = None,
    ):
        self.llm = llm_client
        self.tools = {t.name: t for t in tools}
        self.messages: list[Message] = []

        if system_prompt:
            self.messages.append(Message(role="system", content=system_prompt))
        else:
            self.messages.append(Message(role="system", content=self._default_system_prompt()))

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

    def chat(self, user_input: str) -> str:
        self.messages.append(Message(role="user", content=user_input))

        response = self._execute_loop()

        self.messages.append(Message(role="assistant", content=response.content))
        return response.content

    def _execute_loop(self, max_iterations: int = 10) -> ChatResponse:
        for _ in range(max_iterations):
            tools_schema = [t.to_openai_schema() for t in self.tools.values()]

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
                            tool_call_id=tc.name,
                        )
                    )
                    continue

                result = tool.execute(**tc.arguments)

                tool_result_msg = self._format_tool_result(tc.name, result)
                self.messages.append(tool_result_msg)

            if not response.tool_calls:
                break

        return response

    def _format_tool_result(self, tool_name: str, result: ToolResult) -> Message:
        if result.success:
            content = f"Result: {result.result}"
        else:
            content = f"Error: {result.error}"

        return Message(
            role="tool",
            content=content,
            tool_call_id=tool_name,
        )

    def get_history(self) -> list[Message]:
        return self.messages
