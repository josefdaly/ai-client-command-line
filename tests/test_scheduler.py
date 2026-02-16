import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os
import json

from agentic_cli.services.scheduler import SchedulerService, ScheduledTask


class TestSchedulerServiceParseSchedule:
    def test_parse_at_5pm(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("at 5pm")

        assert cron_expr == "0 17 * * *"
        assert schedule_type == "cron"

    def test_parse_at_9am(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("at 9am")

        assert cron_expr == "0 9 * * *"
        assert schedule_type == "cron"

    def test_parse_at_930am(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("at 9:30 am")

        assert cron_expr == "30 9 * * *"
        assert schedule_type == "cron"

    def test_parse_every_day_at_noon(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("every day at noon")

        assert cron_expr == "0 12 * * *"
        assert schedule_type == "cron"

    def test_parse_every_day_at_midnight(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("every day at midnight")

        assert cron_expr == "0 0 * * *"
        assert schedule_type == "cron"

    def test_parse_every_monday_at_9am(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("every monday at 9am")

        assert cron_expr == "0 9 * * 1"
        assert schedule_type == "cron"

    def test_parse_every_hour(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("every hour")

        assert cron_expr == "0 * * * *"
        assert schedule_type == "cron"

    def test_parse_in_30_minutes(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("in 30 minutes")

        assert "30 minutes" in cron_expr
        assert schedule_type == "at"

    def test_parse_in_2_hours(self):
        service = SchedulerService.__new__(SchedulerService)
        cron_expr, schedule_type, parsed = service._parse_schedule("in 2 hours")

        assert "2 hours" in cron_expr
        assert schedule_type == "at"

    def test_parse_invalid_schedule(self):
        service = SchedulerService.__new__(SchedulerService)

        with pytest.raises(ValueError):
            service._parse_schedule("whenever")


class TestSchedulerService:
    @patch("agentic_cli.services.scheduler.subprocess.run")
    def test_create_task(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "scheduled_tasks.json"
            service = SchedulerService(data_file=data_file)

            task = service.create_task(
                prompt="send a message to joe saying hello", schedule="at 5pm"
            )

            assert task.prompt == "send a message to joe saying hello"
            assert task.schedule == "at 17:00"
            assert task.schedule_type == "cron"
            assert task.status == "pending"
            assert task.id is not None

    @patch("agentic_cli.services.scheduler.subprocess.run")
    def test_list_tasks(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "scheduled_tasks.json"
            service = SchedulerService(data_file=data_file)

            task1 = service.create_task(prompt="task 1", schedule="at 5pm")
            task2 = service.create_task(prompt="task 2", schedule="at 6pm")

            tasks = service.list_tasks()

            assert len(tasks) == 2
            assert tasks[0].prompt == "task 1"
            assert tasks[1].prompt == "task 2"

    @patch("agentic_cli.services.scheduler.subprocess.run")
    def test_get_task(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "scheduled_tasks.json"
            service = SchedulerService(data_file=data_file)

            created = service.create_task(prompt="test task", schedule="at 5pm")
            task = service.get_task(created.id)

            assert task is not None
            assert task.prompt == "test task"

    @patch("agentic_cli.services.scheduler.subprocess.run")
    def test_get_task_not_found(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "scheduled_tasks.json"
            service = SchedulerService(data_file=data_file)

            task = service.get_task("nonexistent-id")

            assert task is None

    @patch("agentic_cli.services.scheduler.subprocess.run")
    def test_cancel_task(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "scheduled_tasks.json"
            service = SchedulerService(data_file=data_file)

            task = service.create_task(prompt="task to cancel", schedule="at 5pm")
            task_id = task.id

            success = service.cancel_task(task_id)

            assert success is True
            assert service.get_task(task_id) is None

    @patch("agentic_cli.services.scheduler.subprocess.run")
    def test_cancel_task_not_found(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "scheduled_tasks.json"
            service = SchedulerService(data_file=data_file)

            success = service.cancel_task("nonexistent-id")

            assert success is False


class TestScheduledTask:
    def test_task_creation(self):
        task = ScheduledTask(
            id="test-id",
            prompt="test prompt",
            schedule="at 5pm",
            cron_expr="0 17 * * *",
            schedule_type="cron",
            llm_provider="opencode",
            llm_model="big-pickle",
            status="pending",
            last_run=None,
            last_result=None,
            last_error=None,
            exit_code=None,
            duration_seconds=None,
            created_at="2024-01-01T10:00:00",
        )

        assert task.id == "test-id"
        assert task.prompt == "test prompt"
        assert task.schedule_type == "cron"
        assert task.status == "pending"
