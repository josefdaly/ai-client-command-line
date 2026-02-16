import sys
import re
from pathlib import Path
from datetime import datetime
import time
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding import KeyBindings

from .config import Config
from .agent import Agent
from .llm.client import get_llm_client
from .tools import ShellTool, FileTool, ScreenTool, XMPPTool, SchedulerTool
from .services.tts import TTSService
from .services.stt import STTService

voice_input = None


style = Style.from_dict(
    {
        "prompt": "ansigreen bold",
        "response": "ansicyan",
        "error": "ansired bold",
    }
)

key_bindings = KeyBindings()


@key_bindings.add("c-v")
def voice_input_handler(event):
    event.app.exit(result="__voice_input__")


def create_agent(config: Config, status_callback=None, tts: Optional[TTSService] = None) -> Agent:
    llm_config = config.llm
    llm_client = get_llm_client(
        provider=llm_config.provider,
        base_url=llm_config.base_url,
        model=llm_config.model,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
    )

    tools = [
        ShellTool(
            allowed_commands=config.tools.allowed_commands,
            forbidden_commands=config.tools.forbidden_commands,
            timeout=config.tools.shell_timeout,
        ),
        FileTool(
            allow_list=config.tools.file_allow_list,
            deny_list=config.tools.file_deny_list,
        ),
        ScreenTool(),
        XMPPTool(),
        SchedulerTool(),
    ]

    tts = TTSService()

    return Agent(llm_client, tools, status_callback=status_callback, tts=tts)


def run_cli(config: Config = None):
    if config is None:
        config = Config.load()

    print("🤖 Starting agentic-cli...")

    def status_handler(status: str, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbols = {
            "thinking": "💭",
            "using_tool": "🔧",
            "tool_complete": "✅",
            "done": "🎉",
        }
        symbol = symbols.get(status, "•")
        print(f"  {symbol} [{timestamp}] {message}")

    try:
        agent = create_agent(config, status_callback=status_handler)
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        sys.exit(1)

    history_file = config.history_file
    history_file.parent.mkdir(parents=True, exist_ok=True)

    session = PromptSession(
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
        style=style,
        key_bindings=key_bindings,
    )

    stt_service = STTService()

    print(f"✨ Connected to {config.llm.model} at {config.llm.base_url}")
    print("Type 'exit' or 'quit' to end the session, 'reset' to clear conversation")
    print("──────────────────────────────────────────────────")

    def wait_for_input():
        if agent.tts:
            agent.tts.wait_until_done()
            while agent.tts.is_speaking:
                time.sleep(0.1)
            time.sleep(0.3)

        print("\r🎤 Listening... (speak or type)", end="", flush=True)
        text = stt_service.listen(timeout=None)
        print("\r                       ", end="\r", flush=True)

        if text:
            if agent.tts:
                agent.tts.speak("Got it")
            print(f"  ✓ Heard")
            return text

        return None

    while True:
        text = wait_for_input()
        if text:
            user_input = text
        else:
            try:
                user_input = session.prompt(">>> ", style=style)
            except KeyboardInterrupt:
                print("\n👋 Exiting...")
                break
            except EOFError:
                break

        if user_input == "__voice_input__":
            text = stt_service.listen(timeout=None)
            if text:
                if agent.tts:
                    agent.tts.speak("Got it")
                print(f"  ✓ Heard")
                user_input = text
            else:
                print("  ⚠️  No speech detected")
                continue

        user_input = user_input.strip()

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("👋 Goodbye! Have a great day!")
            break

        if user_input.lower() == "reset":
            agent.reset()
            print("🗑️  Conversation reset.")
            continue

        try:
            start_time = time.time()
            response, usage = agent.chat(user_input)
            elapsed = time.time() - start_time

            response = re.sub(
                r"<system-reminder[^>]*>.*?</system-reminder>",
                "",
                response,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()
            response = re.sub(
                r"mode has changed.*?permitted.*?\n", "", response, flags=re.IGNORECASE | re.DOTALL
            ).strip()
            response = re.sub(
                r"operational mode.*?(plan|build).*?(read-only|permitted)",
                "",
                response,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            response = re.sub(
                r"your operational mode has changed.*?are needed",
                "",
                response,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            response = re.sub(
                r"\n*<.*?>.*?</.*?>\n*", "", response, flags=re.IGNORECASE | re.DOTALL
            ).strip()
            response = re.sub(
                r"<system-reminder[^>]*>.*?</system-reminder>",
                "",
                response,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()
            response = re.sub(
                r"mode has changed.*?permitted.*?\n",
                "",
                response,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            response = re.sub(
                r"operational mode.*?(plan|build).*?(read-only|permitted)",
                "",
                response,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            response = re.sub(
                r"your operational mode has changed.*?tools as needed",
                "",
                response,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            response = re.sub(r"\n{3,}", "\n\n", response).strip()
            if response:
                print(f"\n{response}")
            prompt_toks = usage.get("prompt_tokens", 0)
            comp_toks = usage.get("completion_tokens", 0)
            total_toks = usage.get("total_tokens", 0)
            print(
                f"\n⏱️  Completed in {elapsed:.2f}s • {prompt_toks:,} in • {comp_toks:,} out • {total_toks:,} total\n"
            )
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Agentic CLI for computer control")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--model", type=str, help="Override model")
    parser.add_argument("--url", type=str, help="Override Ollama URL")
    parser.add_argument("--provider", type=str, help="Override provider (ollama, opencode)")
    parser.add_argument("--api-key", type=str, help="Override API key")
    parser.add_argument("--no-tts", action="store_true", help="Disable text-to-speech")
    args = parser.parse_args()

    config = Config.load(args.config)

    if args.model:
        config.llm.model = args.model

    if args.url:
        config.llm.base_url = args.url
    elif args.provider == "opencode":
        config.llm.base_url = "https://opencode.ai/zen/v1"

    if args.provider:
        config.llm.provider = args.provider
    if args.api_key:
        config.llm.api_key = args.api_key

    run_cli(config)


if __name__ == "__main__":
    main()
