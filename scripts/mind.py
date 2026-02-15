import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, RichLog, Header, Input
from textual.reactive import reactive
from textual import work
from textual.events import Key

from agentic_cli.agent import Agent
from agentic_cli.llm.client import get_llm_client, Message
from agentic_cli.tools import ShellTool, FileTool, ScreenTool


DEFAULT_SYSTEM_PROMPT = """You are an autonomous mind continuously running. Reason, plan, and reflect. 
Write your internal thoughts to files in the thoughts directory when you want to preserve ideas. 
Name your thought files descriptively based on what you're thinking about.
Communicate with the user only when necessary by responding to their messages.
Current time information is provided for context."""


class MindApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    
    #header {
        background: $primary;
        color: $text;
        height: 1;
    }
    
    #main {
        height: 100%;
    }
    
    #chat-pane {
        width: 50%;
        border-right: solid $primary;
    }
    
    #thoughts-pane {
        width: 50%;
    }
    
    .pane-title {
        background: $panel;
        color: $text;
        padding: 0 1;
        height: 1;
    }
    
    #chat-log {
        height: 1fr;
        border: none;
    }
    
    #thoughts-log {
        height: 1fr;
        border: none;
    }
    
    #chat-input {
        height: 3;
        border-top: solid $primary;
    }
    
    #status-bar {
        background: $panel;
        height: 1;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("enter", "send_message", "Send"),
    ]

    chat_messages = reactive([])
    thought_messages = reactive([])
    runtime_remaining = reactive(0)
    thoughts_written = reactive(0)
    messages_processed = reactive(0)

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.start_time = time.time()
        self.thoughts_written_count = 0
        self.responses_written_count = 0
        self.should_stop = False
        self.pending_messages = []

        self.thoughts_dir = Path(args.thoughts_dir)
        self.messages_file = Path(args.messages_file)
        self.thoughts_dir.mkdir(parents=True, exist_ok=True)
        self.messages_file.parent.mkdir(parents=True, exist_ok=True)

        self._init_messages_file()

    def _init_messages_file(self):
        if not self.messages_file.exists():
            self._write_messages({"messages": [], "responses": []})

    def _read_messages(self) -> dict:
        try:
            with open(self.messages_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"messages": [], "responses": []}

    def _write_messages(self, data: dict):
        with open(self.messages_file, "w") as f:
            json.dump(data, f, indent=2)

    def compose(self) -> ComposeResult:
        yield Header(id="header")

        with Horizontal(id="main"):
            with Vertical(id="chat-pane"):
                yield Static("CHAT", classes="pane-title")
                yield RichLog(id="chat-log", auto_scroll=True)
                yield Input(placeholder="Type a message...", id="chat-input")

            with Vertical(id="thoughts-pane"):
                yield Static("THOUGHTS & ACTIONS", classes="pane-title")
                yield RichLog(id="thoughts-log", auto_scroll=True)

        yield Static("", id="status-bar")

    def on_mount(self):
        self.chat_log = self.query_one("#chat-log", RichLog)
        self.thoughts_log = self.query_one("#thoughts-log", RichLog)
        self.status_bar = self.query_one("#status-bar", Static)
        self.chat_input = self.query_one("#chat-input", Input)
        self._run_mind_loop()

    def action_send_message(self):
        message = self.chat_input.value.strip()
        if message:
            self.chat_input.value = ""
            messages_data = self._read_messages()
            messages = messages_data.get("messages", [])
            messages.append(
                {"timestamp": datetime.now().isoformat(), "sender": "user", "content": message}
            )
            messages_data["messages"] = messages
            self._write_messages(messages_data)
            self._log_chat(f"You: {message}")

    def _log_chat(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_log.write(f"[{timestamp}] {message}")

    def _log_thought(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.thoughts_log.write(f"[{timestamp}] {message}")

    def _update_status(self):
        elapsed = time.time() - self.start_time
        remaining = max(0, self.args.runtime - elapsed)
        status = f"Runtime: {int(remaining)}s | Thoughts: {self.thoughts_written_count}/{self.args.max_thoughts} | Responses: {self.responses_written_count}/{self.args.max_responses} | Elapsed: {elapsed:.1f}s"
        self.status_bar.update(status)

    def _check_stop(self) -> bool:
        if self.should_stop:
            return True

        elapsed = time.time() - self.start_time
        if elapsed >= self.args.runtime:
            self._log_thought("Runtime complete. Shutting down...")
            return True

        return False

    @work(exclusive=True, thread=True)
    def _run_mind_loop(self):
        self._log_thought("Initializing mind simulation...")

        llm_client = get_llm_client(
            provider=self.args.provider,
            base_url=self.args.url,
            model=self.args.model,
            temperature=0.7,
            max_tokens=4096,
        )

        tools = [
            ShellTool(
                allowed_commands=self.args.allowed_commands,
                forbidden_commands=["rm -rf /", ":(){:|:&};:", "mkfs"],
                timeout=self.args.shell_timeout,
            ),
            FileTool(allow_list=[str(self.thoughts_dir.absolute())]),
            ScreenTool(),
        ]

        system_prompt = self.args.system_prompt or DEFAULT_SYSTEM_PROMPT
        if self.args.system_prompt_file:
            prompt_path = Path(self.args.system_prompt_file)
            if prompt_path.exists():
                system_prompt = prompt_path.read_text()

        self.agent = Agent(llm_client, tools, system_prompt=system_prompt)

        self._log_thought(f"Agent initialized with model: {self.args.model}")
        self._log_thought(f"Thoughts directory: {self.thoughts_dir}")
        self._log_thought(f"Runtime: {self.args.runtime}s")

        iteration = 0
        while not self._check_stop():
            iteration += 1
            elapsed = time.time() - self.start_time

            messages_data = self._read_messages()
            new_messages = messages_data.get("messages", [])

            user_messages = []
            for msg in new_messages:
                content = msg.get("content", "").lower()
                if content in ["stop", "shutdown", "quit"]:
                    self._log_thought("Stop command received. Shutting down...")
                    self.should_stop = True
                    break
                user_messages.append(msg)

            if user_messages:
                messages_data["messages"] = []
                self._write_messages(messages_data)

            if user_messages and self.responses_written_count < self.args.max_responses:
                self.messages_processed = len(user_messages)
                for msg in user_messages:
                    self._log_chat(f"User: {msg.get('content', '')}")

                if self.args.verbose:
                    self._log_thought(f"Processing {len(user_messages)} new message(s)")

            time_info = f"Elapsed time: {int(elapsed)} seconds"

            if user_messages:
                user_content = time_info + "\n\nUser messages:\n"
                for msg in user_messages:
                    user_content += f"- {msg.get('content', '')}\n"
                user_content += "\nRespond to the user if necessary. You may also write thoughts to files or use tools."
            else:
                user_content = (
                    time_info
                    + "\n\nContinue reasoning, reflecting, or acting. You may write thoughts to files, use tools, or wait."
                )

            self._log_thought(f"Iteration {iteration}: {time_info}")

            try:
                self.agent.messages.append(Message(role="user", content=user_content))

                response, usage = self.agent.chat(user_content)

                if self.args.verbose:
                    self._log_thought(f"Response: {response[:100]}...")

                has_tool_calls = (
                    hasattr(self.agent.messages[-1], "tool_calls")
                    and self.agent.messages[-1].tool_calls
                )

                if has_tool_calls:
                    for msg in reversed(self.agent.messages):
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tool_name = tc.name
                                args = tc.arguments if isinstance(tc.arguments, dict) else {}

                                if tool_name == "files" and args.get("operation") == "write":
                                    if self.thoughts_written_count < self.args.max_thoughts:
                                        filename = args.get("path", "thought.txt")
                                        self.thoughts_written_count += 1
                                        self.thoughts_written = self.thoughts_written_count
                                        self._log_thought(f"Wrote thought file: {filename}")
                                    else:
                                        self._log_thought("Max thoughts reached, not writing")

                            break

                response_lower = response.lower().strip()
                if response_lower and self.responses_written_count < self.args.max_responses:
                    messages_data = self._read_messages()
                    responses = messages_data.get("responses", [])
                    responses.append({"timestamp": datetime.now().isoformat(), "content": response})
                    messages_data["responses"] = responses
                    self._write_messages(messages_data)

                    self.responses_written_count += 1
                    self._log_chat(f"Mind: {response}")

                    if self.args.verbose:
                        self._log_thought("Response written to message queue")

            except Exception as e:
                self._log_thought(f"Error: {e}")
                if self.args.verbose:
                    import traceback

                    self._log_thought(traceback.format_exc())

            self._update_status()
            time.sleep(self.args.sleep)

        self._log_thought("Mind simulation complete.")
        self._log_chat("--- Session Ended ---")


def main():
    parser = argparse.ArgumentParser(description="Mind Simulation - Autonomous AI Agent")

    parser.add_argument("--runtime", type=int, default=30, help="Runtime in seconds (default: 30)")
    parser.add_argument("--model", type=str, default="qwen3:30b-a3b", help="LLM model")
    parser.add_argument("--url", type=str, default="http://home-base:11434", help="LLM base URL")
    parser.add_argument(
        "--provider",
        type=str,
        default="ollama",
        choices=["ollama", "opencode"],
        help="LLM provider",
    )
    parser.add_argument("--api-key", type=str, help="API key for OpenCode provider")
    parser.add_argument("--system-prompt", type=str, help="Custom system prompt")
    parser.add_argument("--system-prompt-file", type=str, help="Load system prompt from file")
    parser.add_argument("--thoughts-dir", type=str, default="thoughts/", help="Thoughts directory")
    parser.add_argument(
        "--messages-file", type=str, default="data/mind_messages.json", help="Messages JSON file"
    )
    parser.add_argument(
        "--sleep", type=float, default=1.0, help="Sleep between iterations (default: 1)"
    )
    parser.add_argument(
        "--max-thoughts", type=int, default=5, help="Max thought files (default: 5)"
    )
    parser.add_argument("--max-responses", type=int, default=10, help="Max responses (default: 10)")
    parser.add_argument(
        "--shell-timeout", type=int, default=30, help="Shell command timeout (default: 30)"
    )
    parser.add_argument(
        "--allowed-commands", type=str, nargs="*", help="Allowed shell commands (whitelist)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    app = MindApp(args)
    app.run()


if __name__ == "__main__":
    main()
