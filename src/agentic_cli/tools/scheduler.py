from pathlib import Path
from typing import Optional

from .base import Tool, ToolResult
from ..services.scheduler import SchedulerService


class SchedulerTool(Tool):
    def __init__(self, data_file: Optional[Path] = None):
        self._service: Optional[SchedulerService] = None
        self.data_file = data_file

    def _get_service(self) -> SchedulerService:
        if self._service is None:
            self._service = SchedulerService(self.data_file)
        return self._service

    @property
    def name(self) -> str:
        return "scheduler"

    @property
    def description(self) -> str:
        return """Schedule tasks to run at specific times. Use this tool to schedule prompts to run later.

IMPORTANT: When scheduling tasks, preserve ALL contextual information in the prompt including:
- Recipients (e.g., email addresses, JIDs, phone numbers)
- Message content or task details
- Any specific instructions

Do NOT decontextualize or simplify the prompt. For example:
- If user says "send a hello message to joe@hackerchat.net in 2 minutes", use prompt="Send a hello message to joe@hackerchat.net"
- If user says "remind me to call mom at 5pm", use prompt="Call mom"

You can schedule tasks using natural language like:
- "at 5pm" - Run once at 5pm today
- "at 9am" - Run once at 9am
- "every day at noon" - Run daily at noon
- "every monday at 9am" - Run every Monday at 9am
- "every hour" - Run every hour
- "in 30 minutes" - Run once in 30 minutes
- "in 2 hours" - Run once in 2 hours"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: schedule, list, or cancel",
                    "enum": ["schedule", "list", "cancel"],
                },
                "prompt": {
                    "type": "string",
                    "description": "The prompt or message to execute (required for schedule action)",
                },
                "message": {
                    "type": "string",
                    "description": "Alias for prompt - the message to send (required for schedule action)",
                },
                "schedule": {
                    "type": "string",
                    "description": "When to run (e.g., 'at 5pm', 'every monday at 9am', 'in 30 minutes')",
                },
                "task_id": {
                    "type": "string",
                    "description": "The task ID to cancel (required for cancel action)",
                },
                "llm_provider": {
                    "type": "string",
                    "description": "Optional LLM provider to use for this task",
                },
                "llm_model": {
                    "type": "string",
                    "description": "Optional LLM model to use for this task",
                },
            },
            "required": ["action"],
        }

    def execute(
        self,
        action: str,
        prompt: Optional[str] = None,
        schedule: Optional[str] = None,
        task_id: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        # Use message as alias for prompt
        if message and not prompt:
            prompt = message
        try:
            service = self._get_service()

            if action == "schedule":
                if not prompt:
                    return ToolResult(
                        success=False, result=None, error="prompt is required for schedule action"
                    )
                if not schedule:
                    return ToolResult(
                        success=False, result=None, error="schedule is required for schedule action"
                    )

                task = service.create_task(
                    prompt=prompt, schedule=schedule, llm_provider=llm_provider, llm_model=llm_model
                )

                return ToolResult(
                    success=True,
                    result=f"Task scheduled successfully!\n"
                    f"  ID: {task.id}\n"
                    f"  Prompt: {task.prompt}\n"
                    f"  Schedule: {task.schedule}\n"
                    f"  Type: {task.schedule_type}\n"
                    f"  Status: {task.status}",
                )

            elif action == "list":
                tasks = service.list_tasks()

                if not tasks:
                    return ToolResult(success=True, result="No scheduled tasks.")

                result = "Scheduled Tasks:\n\n"
                for task in tasks:
                    result += f"ID: {task.id}\n"
                    result += f"  Prompt: {task.prompt}\n"
                    result += f"  Schedule: {task.schedule}\n"
                    result += f"  Type: {task.schedule_type}\n"
                    result += f"  Status: {task.status}\n"
                    result += f"  Last Run: {task.last_run or 'Never'}\n"
                    if task.last_error:
                        result += f"  Last Error: {task.last_error}\n"
                    result += "\n"

                return ToolResult(success=True, result=result)

            elif action == "cancel":
                if not task_id:
                    return ToolResult(
                        success=False, result=None, error="task_id is required for cancel action"
                    )

                success = service.cancel_task(task_id)

                if success:
                    return ToolResult(
                        success=True, result=f"Task {task_id} cancelled successfully."
                    )
                else:
                    return ToolResult(success=False, result=None, error=f"Task {task_id} not found")

            else:
                return ToolResult(
                    success=False,
                    result=None,
                    error=f"Unknown action: {action}. Use 'schedule', 'list', or 'cancel'.",
                )

        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
