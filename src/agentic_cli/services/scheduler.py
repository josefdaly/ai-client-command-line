import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class ScheduledTask:
    id: str
    prompt: str
    schedule: str
    cron_expr: Optional[str]
    schedule_type: str  # "cron" or "at"
    llm_provider: str
    llm_model: str
    status: str  # "pending", "running", "completed", "failed"
    scheduled_at: Optional[str]  # ISO timestamp when task should run
    last_run: Optional[str]
    last_result: Optional[str]
    last_error: Optional[str]
    exit_code: Optional[int]
    duration_seconds: Optional[float]
    created_at: str


class SchedulerService:
    DEFAULT_LLM_PROVIDER = "ollama"
    DEFAULT_LLM_MODEL = "qwen3:30b-a3b"

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or Path("data/scheduled_tasks.json")
        self._ensure_data_file()

    def _ensure_data_file(self):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self._write_tasks({"tasks": []})

    def _get_daemon_paths(self) -> tuple[Path, Path]:
        """Get paths to daemon script and venv python."""
        project_root = self.data_file.parent.parent
        daemon_script = project_root / "scripts" / "scheduler_daemon.py"
        venv_python = project_root / ".venv" / "bin" / "python"
        return daemon_script, venv_python

    def _start_daemon(self):
        """Start the scheduler daemon if not already running."""
        daemon_script, venv_python = self._get_daemon_paths()

        if not daemon_script.exists():
            return

        result = subprocess.run(
            ["pgrep", "-f", "scheduler_daemon.py"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return

        subprocess.Popen(
            [str(venv_python), str(daemon_script), "--poll-interval", "30"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _stop_daemon(self):
        """Stop the scheduler daemon."""
        subprocess.run(["pkill", "-f", "scheduler_daemon.py"], capture_output=True)

    def _has_pending_at_tasks(self) -> bool:
        """Check if there are any pending at-style tasks."""
        tasks = self.list_tasks()
        return any(t.schedule_type == "at" and t.status == "pending" for t in tasks)

    def _read_tasks(self) -> dict:
        try:
            with open(self.data_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"tasks": []}

    def _write_tasks(self, data: dict):
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def _parse_schedule(self, schedule: str) -> tuple[str, str, str]:
        """Parse natural language schedule to cron/at expression.

        Returns: (cron_expr, schedule_type, parsed_schedule)
        """
        schedule = schedule.lower().strip()

        # "in X minutes" or "in X hours" - use at command
        in_minutes_match = re.match(r"in\s+(\d+)\s+minutes?", schedule)
        if in_minutes_match:
            minutes = int(in_minutes_match.group(1))
            return (f"now + {minutes} minutes", "at", f"in {minutes} minutes")

        in_hours_match = re.match(r"in\s+(\d+)\s+hours?", schedule)
        if in_hours_match:
            hours = int(in_hours_match.group(1))
            return (f"now + {hours} hours", "at", f"in {hours} hours")

        # "at Xam" or "at Xpm" or "at X:XX"
        at_match = re.match(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", schedule)
        if at_match:
            hour = int(at_match.group(1))
            minute = int(at_match.group(2) or 0)
            period = at_match.group(3)

            if period == "am" and hour == 12:
                hour = 0
            elif period == "pm" and hour != 12:
                hour += 12

            cron_expr = f"{minute} {hour} * * *"
            return (cron_expr, "cron", f"at {hour:02d}:{minute:02d}")

        # "every day at noon" or "every day at midnight"
        if "noon" in schedule:
            return ("0 12 * * *", "cron", "every day at noon")
        if "midnight" in schedule:
            return ("0 0 * * *", "cron", "every day at midnight")

        # "every X" - recurring
        every_hour_match = re.match(r"every\s+hour", schedule)
        if every_hour_match:
            return ("0 * * * *", "cron", "every hour")

        # "every day at X"
        daily_match = re.match(r"every\s+day\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", schedule)
        if daily_match:
            hour = int(daily_match.group(1))
            minute = int(daily_match.group(2) or 0)
            period = daily_match.group(3)

            if period == "am" and hour == 12:
                hour = 0
            elif period == "pm" and hour != 12:
                hour += 12

            cron_expr = f"{minute} {hour} * * *"
            return (cron_expr, "cron", f"every day at {hour:02d}:{minute:02d}")

        # Days of week
        day_map = {
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
            "sunday": 0,
        }
        for day_name, day_num in day_map.items():
            day_match = re.match(
                rf"every\s+{day_name}\s+at\s+(\d{{1,2}})(?::(\d{{2}}))?\s*(am|pm)?", schedule
            )
            if day_match:
                hour = int(day_match.group(1))
                minute = int(day_match.group(2) or 0)
                period = day_match.group(3)

                if period == "am" and hour == 12:
                    hour = 0
                elif period == "pm" and hour != 12:
                    hour += 12

                cron_expr = f"{minute} {hour} * * {day_num}"
                return (cron_expr, "cron", f"every {day_name} at {hour:02d}:{minute:02d}")

        # Default: error
        raise ValueError(f"Could not parse schedule: {schedule}")

    def _calculate_scheduled_at(
        self, schedule: str, schedule_type: str, cron_expr: Optional[str]
    ) -> Optional[str]:
        """Calculate the ISO timestamp when the task should run."""
        from datetime import timedelta

        schedule = schedule.lower().strip()
        now = datetime.now()

        # For "at" type tasks (in X minutes/hours)
        if schedule_type == "at":
            # "in X minutes"
            match = re.match(r"in\s+(\d+)\s+minutes?", schedule)
            if match:
                minutes = int(match.group(1))
                return (now + timedelta(minutes=minutes)).isoformat()

            # "in X hours"
            match = re.match(r"in\s+(\d+)\s+hours?", schedule)
            if match:
                hours = int(match.group(1))
                return (now + timedelta(hours=hours)).isoformat()

        # For cron type tasks, calculate next occurrence
        if schedule_type == "cron" and cron_expr:
            # Parse cron expression and calculate next run time
            try:
                parts = cron_expr.split()
                if len(parts) >= 5:
                    minute, hour, _, _, _ = parts[:5]
                    # Calculate next occurrence
                    next_run = now.replace(second=0, microsecond=0)

                    # Handle minute
                    if minute == "*":
                        pass
                    else:
                        next_run = next_run.replace(minute=int(minute))

                    # Handle hour
                    if hour == "*":
                        pass
                    else:
                        next_run = next_run.replace(hour=int(hour))

                    # If the time has passed today, move to next day
                    if next_run <= now:
                        next_run = next_run + timedelta(days=1)

                    return next_run.isoformat()
            except Exception:
                pass

        return None

    def create_task(
        self,
        prompt: str,
        schedule: str,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> ScheduledTask:
        """Create a new scheduled task."""
        cron_expr, schedule_type, parsed_schedule = self._parse_schedule(schedule)

        # Calculate scheduled_at timestamp
        scheduled_at = self._calculate_scheduled_at(schedule, schedule_type, cron_expr)

        task = ScheduledTask(
            id=str(uuid.uuid4()),
            prompt=prompt,
            schedule=parsed_schedule,
            cron_expr=cron_expr,
            schedule_type=schedule_type,
            llm_provider=llm_provider or self.DEFAULT_LLM_PROVIDER,
            llm_model=llm_model or self.DEFAULT_LLM_MODEL,
            status="pending",
            scheduled_at=scheduled_at,
            last_run=None,
            last_result=None,
            last_error=None,
            exit_code=None,
            duration_seconds=None,
            created_at=datetime.now().isoformat(),
        )

        # Add to JSON
        data = self._read_tasks()
        data["tasks"].append(asdict(task))
        self._write_tasks(data)

        # Add to cron/at
        if schedule_type == "cron":
            self._add_to_cron(task)
        else:
            self._add_to_at(task)
            # Start daemon for at-style tasks
            self._start_daemon()

        return task

    def list_tasks(self) -> list[ScheduledTask]:
        """List all scheduled tasks."""
        data = self._read_tasks()
        tasks = []
        for task_data in data.get("tasks", []):
            tasks.append(ScheduledTask(**task_data))
        return tasks

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a specific task by ID."""
        tasks = self.list_tasks()
        for task in tasks:
            if task.id == task_id:
                return task
        return None

    def cancel_task(self, task_id: str) -> bool:
        """Cancel and remove a scheduled task."""
        task = self.get_task(task_id)
        if not task:
            return False

        # Remove from cron/at
        if task.schedule_type == "cron":
            self._remove_from_cron(task)
        else:
            self._remove_from_at(task)

        # Remove from JSON
        data = self._read_tasks()
        data["tasks"] = [t for t in data.get("tasks", []) if t["id"] != task_id]
        self._write_tasks(data)

        return True

    def update_task_status(
        self,
        task_id: str,
        status: str,
        last_result: Optional[str] = None,
        last_error: Optional[str] = None,
        exit_code: Optional[int] = None,
        duration_seconds: Optional[float] = None,
    ):
        """Update task status after execution."""
        data = self._read_tasks()
        for task_data in data.get("tasks", []):
            if task_data["id"] == task_id:
                task_data["status"] = status
                task_data["last_run"] = datetime.now().isoformat()
                if last_result is not None:
                    task_data["last_result"] = last_result
                if last_error is not None:
                    task_data["last_error"] = last_error
                if exit_code is not None:
                    task_data["exit_code"] = exit_code
                if duration_seconds is not None:
                    task_data["duration_seconds"] = duration_seconds
                break
        self._write_tasks(data)

    def _get_runner_path(self) -> str:
        """Get absolute path to the scheduler runner script."""
        script_dir = Path(__file__).parent.parent.parent.parent / "scripts"
        return str(script_dir / "scheduler_runner.py")

    def _add_to_cron(self, task: ScheduledTask):
        """Add a cron entry for the task."""
        if not task.cron_expr:
            return

        runner_path = self._get_runner_path()

        # Use explicit path to venv python
        project_root = Path(__file__).parent.parent.parent.parent
        venv_python = project_root / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = Path("python3")

        cron_line = f"{task.cron_expr} {venv_python} {runner_path} --task-id={task.id}"

        # Get current crontab
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            current_crontab = result.stdout if result.returncode == 0 else ""
        except Exception:
            current_crontab = ""

        # Check if already exists
        if task.id in current_crontab:
            return

        # Add new line
        new_crontab = current_crontab.rstrip() + "\n" + cron_line + "\n"

        # Set new crontab
        subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)

    def _remove_from_cron(self, task: ScheduledTask):
        """Remove a cron entry for the task."""
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if result.returncode != 0:
                return

            lines = result.stdout.split("\n")
            new_lines = [line for line in lines if task.id not in line]
            new_crontab = "\n".join(new_lines)

            subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
        except Exception:
            pass

    def _add_to_at(self, task: ScheduledTask):
        """Add an at entry for one-time task."""
        runner_path = self._get_runner_path()

        # at accepts relative times like "now + 30 minutes"
        at_time = task.cron_expr  # We store the "now + X" expression in cron_expr for at tasks

        # Copy current environment and add task ID and venv to PATH
        env = os.environ.copy()
        env["SCHEDULER_TASK_ID"] = task.id

        # Add venv Python to PATH - venv is in project root, not src
        project_root = Path(__file__).parent.parent.parent.parent
        venv_bin = project_root / ".venv" / "bin"
        if venv_bin.exists():
            env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"

        # Use echo to pipe command to at (so shell interprets shebang)
        python_cmd = str(venv_bin / "python") if venv_bin.exists() else "python3"
        at_command = f"PATH={venv_bin}:$PATH {python_cmd} {runner_path} --task-id={task.id}"

        try:
            subprocess.run(
                ["sh", "-c", f"echo '{at_command}' | at -v {at_time}"],
                env=env,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to schedule 'at' command: {e}")

    def _remove_from_at(self, task: ScheduledTask):
        """Remove an at entry."""
        try:
            # Find and remove the at job
            result = subprocess.run(["atq"], capture_output=True, text=True)
            # This is complex - at jobs don't have IDs we can easily match
            # For now, we'll leave orphaned at jobs and clean them up on task list
            pass
        except Exception:
            pass
