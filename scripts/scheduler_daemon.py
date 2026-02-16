#!/usr/bin/env python3
"""
Simple scheduler daemon that polls for pending tasks.

Usage:
    scheduler_daemon.py
    scheduler_daemon.py --poll-interval 30
"""

import argparse
import time
import sys
from pathlib import Path

# Add src to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
src_path = project_root / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from agentic_cli.llm.client import get_llm_client, Message
from agentic_cli.services.scheduler import SchedulerService
from agentic_cli.tools import XMPPTool


def run_task(task_id: str, data_file: Path):
    """Run a single task."""
    import json

    with open(data_file) as f:
        data = json.load(f)

    task = None
    for t in data.get("tasks", []):
        if t["id"] == task_id:
            task = t
            break

    if not task:
        print(f"Task {task_id} not found")
        return

    service = SchedulerService(data_file)
    service.update_task_status(task_id, "running")

    start_time = time.time()

    try:
        llm_client = get_llm_client(
            provider=task.get("llm_provider", "ollama"),
            base_url="http://home-base:11434",
            model=task.get("llm_model", "qwen3:30b-a3b"),
            temperature=0.7,
            max_tokens=4096,
        )

        xmpp_tool = XMPPTool()
        tools = [xmpp_tool.to_openai_schema()]

        messages = [Message(role="user", content=task["prompt"])]
        response = llm_client.chat(messages, tools=tools)

        tool_results = []
        if response.tool_calls:
            for tc in response.tool_calls:
                func_name = tc.name
                func_args = tc.arguments
                print(f"Executing tool: {func_name}")
                if func_name == "xmpp":
                    result = xmpp_tool.execute(**func_args)
                    tool_results.append({"tool": func_name, "result": result.model_dump()})
                    print(f"Tool result: {result.success}")

        duration = time.time() - start_time

        result_summary = response.content
        if tool_results:
            result_summary += "\n\nTool results:\n" + "\n".join(
                f"- {r['tool']}: {r['result'].get('success')}" for r in tool_results
            )

        service.update_task_status(
            task_id, "completed", last_result=result_summary, exit_code=0, duration_seconds=duration
        )

        if task.get("schedule_type") == "at":
            with open(data_file) as f:
                data = json.load(f)
            data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
            with open(data_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"Removed one-off task {task_id}")

        print(f"Task {task_id} completed in {duration:.2f}s")

        # Check if we should exit (no more pending at tasks)
        if task.get("schedule_type") == "at":
            with open(data_file) as f:
                data = json.load(f)
            remaining_at_tasks = [
                t
                for t in data.get("tasks", [])
                if t.get("schedule_type") == "at" and t.get("status") == "pending"
            ]
            if not remaining_at_tasks:
                print("No more pending at tasks. Exiting.")
                sys.exit(0)

    except Exception as e:
        duration = time.time() - start_time
        service.update_task_status(
            task_id, "failed", last_error=str(e), exit_code=1, duration_seconds=duration
        )
        print(f"Task {task_id} failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Scheduler daemon")
    parser.add_argument("--poll-interval", type=int, default=30, help="Poll interval in seconds")
    args = parser.parse_args()

    data_file = project_root / "data" / "scheduled_tasks.json"

    print(f"Scheduler daemon started. Polling every {args.poll_interval}s...")

    while True:
        try:
            import json
            from datetime import datetime

            with open(data_file) as f:
                data = json.load(f)

            now = datetime.now()
            for task in data.get("tasks", []):
                if task["status"] == "pending":
                    # Check if it's time to run
                    scheduled_at = task.get("scheduled_at")
                    if scheduled_at:
                        scheduled_time = datetime.fromisoformat(scheduled_at)
                        if scheduled_time > now:
                            # Not time yet, skip
                            continue

                    print(f"Running pending task: {task['id']}")
                    run_task(task["id"], data_file)

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
