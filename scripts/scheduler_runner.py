#!/Users/joseph.daly/Documents/personal_projects/ai-sandbox/.venv/bin/python
"""
Standalone scheduler runner for cron jobs.

This script is called by cron to execute scheduled tasks.
It loads the task from the JSON file, executes the prompt via the LLM,
and logs the results.

Usage:
    scheduler_runner.py --task-id=<uuid>

Environment variables:
    SCHEDULER_TASK_ID: Alternative way to pass task ID (for at command)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent
src_path = project_root / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from agentic_cli.llm.client import get_llm_client
from agentic_cli.services.scheduler import SchedulerService
from agentic_cli.tools import XMPPTool


def main():
    parser = argparse.ArgumentParser(description="Run a scheduled task")
    parser.add_argument("--task-id", type=str, help="Task ID to run")
    args = parser.parse_args()

    # Get task ID from args or environment
    task_id = args.task_id or os.environ.get("SCHEDULER_TASK_ID")

    if not task_id:
        print("Error: No task ID provided. Use --task-id or set SCHEDULER_TASK_ID")
        sys.exit(1)

    # Find the data file
    data_file = project_root / "data" / "scheduled_tasks.json"

    if not data_file.exists():
        print(f"Error: Task data file not found: {data_file}")
        sys.exit(1)

    # Load tasks
    with open(data_file) as f:
        data = json.load(f)

    # Find the task
    task = None
    for t in data.get("tasks", []):
        if t["id"] == task_id:
            task = t
            break

    if not task:
        print(f"Error: Task {task_id} not found")
        sys.exit(1)

    print(f"Running task {task_id}: {task['prompt']}")

    # Update status to running
    service = SchedulerService(data_file)
    service.update_task_status(task_id, "running")

    start_time = time.time()

    try:
        # Get LLM client
        llm_client = get_llm_client(
            provider=task.get("llm_provider", "ollama"),
            base_url="http://home-base:11434",
            model=task.get("llm_model", "qwen3:30b-a3b"),
            temperature=0.7,
            max_tokens=4096,
        )

        # Get tools
        xmpp_tool = XMPPTool()
        tools = [xmpp_tool.to_openai_schema()]

        # Execute the prompt with tools
        from agentic_cli.llm.client import Message

        messages = [Message(role="user", content=task["prompt"])]

        # First call to get tool call
        response = llm_client.chat(messages, tools=tools)

        # Execute tool calls if any
        tool_results = []
        if response.tool_calls:
            for tc in response.tool_calls:
                func_name = tc.name
                func_args = tc.arguments

                print(f"Executing tool: {func_name}")
                if func_name == "xmpp":
                    result = xmpp_tool.execute(**func_args)
                    tool_results.append({"tool": func_name, "result": result.model_dump()})
                    print(f"Tool result: {result.success}, {result.result or result.error}")

        duration = time.time() - start_time

        # Log success
        result_summary = response.content
        if tool_results:
            result_summary += "\n\nTool results:\n" + "\n".join(
                f"- {r['tool']}: {r['result'].get('success')}" for r in tool_results
            )

        service.update_task_status(
            task_id,
            "completed",
            last_result=result_summary,
            exit_code=0,
            duration_seconds=duration,
        )

        # Remove one-off at tasks from JSON after completion (at jobs auto-remove after running)
        if task.get("schedule_type") == "at":
            with open(data_file) as f:
                data = json.load(f)
            data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
            with open(data_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"Removed one-off task {task_id} from schedule")

        print(f"Task completed successfully in {duration:.2f}s")
        print(f"Response: {response.content[:200]}...")

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)

        # Log failure
        service.update_task_status(
            task_id, "failed", last_error=error_msg, exit_code=1, duration_seconds=duration
        )

        print(f"Task failed after {duration:.2f}s")
        print(f"Error: {error_msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
