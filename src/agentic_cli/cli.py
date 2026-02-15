import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from .config import Config
from .agent import Agent
from .llm.client import get_llm_client
from .tools import ShellTool, FileTool, ScreenTool


style = Style.from_dict(
    {
        "prompt": "ansigreen bold",
        "response": "ansiyellow",
        "error": "ansired bold",
    }
)


def create_agent(config: Config) -> Agent:
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
    ]

    return Agent(llm_client, tools)


def run_cli(config: Config = None):
    if config is None:
        config = Config.load()

    print("Initializing agentic-cli...")

    try:
        agent = create_agent(config)
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        sys.exit(1)

    history_file = config.history_file
    history_file.parent.mkdir(parents=True, exist_ok=True)

    session = PromptSession(
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
        style=style,
    )

    print(f"Connected to {config.llm.provider} ({config.llm.model})")
    print("Type 'exit' or 'quit' to end the session, 'reset' to clear conversation")
    print("---")

    while True:
        try:
            user_input = session.prompt(">>> ", style=style)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except EOFError:
            break

        user_input = user_input.strip()

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if user_input.lower() == "reset":
            agent.reset()
            print("Conversation reset.")
            continue

        try:
            response = agent.chat(user_input)
            print(f"\n{response}\n")
        except Exception as e:
            print(f"Error: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Agentic CLI for computer control")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--model", type=str, help="Override model")
    parser.add_argument("--url", type=str, help="Override Ollama URL")
    args = parser.parse_args()

    config = Config.load(args.config)

    if args.model:
        config.llm.model = args.model
    if args.url:
        config.llm.base_url = args.url

    run_cli(config)


if __name__ == "__main__":
    main()
