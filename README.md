# Agentic CLI

A Python-based agentic platform for controlling your computer via semantic commands from the CLI.

## Features

- **Shell Commands** - Execute shell commands with safety guards
- **File Operations** - Read, write, list, search, and manage files
- **Screen Awareness** - Capture screenshots and get display info
- **Interactive REPL** - Conversational interface with history
- **Model Agnostic** - Works with any Ollama model

## Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) package manager
- [Ollama](https://ollama.ai) installed and running

## Setup

### 1. Install uv

```bash
# macOS
brew install uv

# Or via curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Pull an Ollama Model

```bash
ollama pull llama3.2
```

Or any other model:
```bash
ollama pull codellama
ollama pull mistral
```

### 3. Configure (Optional)

Create `~/.agentic_cli/config.yaml`:

```yaml
llm:
  provider: ollama
  base_url: http://localhost:11434
  model: llama3.2
  temperature: 0.7
  max_tokens: 4096

tools:
  shell_timeout: 30
  forbidden_commands:
    - "rm -rf /"
    - ":(){:|:&};:"
    - mkfs
```

## Usage

### Interactive Mode

```bash
uv run src/agentic_cli
```

Commands:
- Type your request naturally
- `reset` - Clear conversation history
- `exit` or `quit` - Exit the CLI

### Command Line Options

```bash
uv run src/agentic_cli --model llama3.2 --url http://localhost:11434
```

## Architecture

```
src/agentic_cli/
├── agent.py          # Agent loop with tool calling
├── cli.py            # Interactive REPL
├── config.py         # Configuration management
├── llm/
│   └── client.py     # Ollama client
└── tools/
    ├── base.py       # Tool abstract class
    ├── shell.py      # Shell execution
    ├── files.py      # File operations
    └── screen.py     # Screenshots
```

## API

### Tools

#### ShellTool

Execute shell commands.

```python
from agentic_cli.tools import ShellTool

tool = ShellTool(
    allowed_commands=["git", "ls"],    # Optional whitelist
    forbidden_commands=["rm -rf /"],    # Default blocked commands
    timeout=30                          # Command timeout (seconds)
)

result = tool.execute(command="ls -la")
# ToolResult(success=True, result="...", error=None)
```

#### FileTool

Read, write, and manage files.

```python
from agentic_cli.tools import FileTool

tool = FileTool(
    allow_list=["/home/user/projects"],  # Optional directory whitelist
    deny_list=["/etc", "/root"]          # Blocked directories
)

# Read
tool.execute(operation="read", path="/path/to/file.txt")

# Write
tool.execute(operation="write", path="/path/to/file.txt", content="Hello")

# List
tool.execute(operation="list", path="/path/to/dir")

# Exists
tool.execute(operation="exists", path="/path/to/file.txt")

# Search
tool.execute(operation="search", path="/path/to/dir", pattern="*.py")

# Info
tool.execute(operation="info", path="/path/to/file.txt")

# Delete
tool.execute(operation="delete", path="/path/to/file.txt")
```

#### ScreenTool

Capture screenshots and get display info.

```python
from agentic_cli.tools import ScreenTool

tool = ScreenTool(save_dir="/tmp/screenshots")

# Screenshot
result = tool.execute(operation="capture")
result = tool.execute(operation="capture", path="/tmp/screenshot.png")

# Display info
result = tool.execute(operation="info")
```

### Agent

```python
from agentic_cli.agent import Agent
from agentic_cli.llm.client import OllamaClient
from agentic_cli.tools import ShellTool, FileTool, ScreenTool

llm = OllamaClient(
    base_url="http://localhost:11434",
    model="llama3.2"
)

tools = [
    ShellTool(),
    FileTool(),
    ScreenTool()
]

agent = Agent(llm, tools, system_prompt="Your custom prompt")

response = agent.chat("List files in the current directory")
print(response)

agent.reset()  # Clear conversation history
```

### Configuration

```python
from agentic_cli.config import Config, LLMConfig, ToolConfig

# Default config
config = Config()

# Custom config
config = Config(
    llm=LLMConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="llama3.2",
        temperature=0.7,
        max_tokens=4096
    ),
    tools=ToolConfig(
        shell_timeout=30,
        forbidden_commands=["rm -rf /"]
    )
)

# Save/Load
config.save(path="/path/to/config.yaml")
config = Config.load(path="/path/to/config.yaml")
```

## Testing

```bash
uv run pytest tests/ -v
```

With coverage:
```bash
uv run pytest tests/ --cov=src/agentic_cli
```

## Security Notes

- Shell tool has forbidden command protection by default
- File tool supports allowlists to restrict accessible directories
- Always review commands before execution
- Consider running in a container/VM for production use
