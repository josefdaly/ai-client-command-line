import pytest
from agentic_cli.agent import clean_response


class TestCleanResponse:
    def test_removes_system_reminder_tags(self):
        response = """Hello world
<system-reminder>
Your operational mode has changed from plan to build.
</system-reminder>
How can I help?"""

        result = clean_response(response)

        assert "<system-reminder>" not in result
        assert "</system-reminder>" not in result
        assert "Hello world" in result
        assert "How can I help?" in result

    def test_removes_mode_changed_message(self):
        response = """Some response
mode has changed from plan to build.
You are no longer in read-only mode.
permitted to make changes.

More content"""

        result = clean_response(response)

        assert "mode has changed" not in result
        assert "More content" in result

    def test_removes_operational_mode(self):
        response = """Initial response
operational mode has changed from plan to build
You are no longer in read-only mode. You are permitted to make file changes.
        
Final answer."""

        result = clean_response(response)

        assert "operational mode" not in result.lower()
        assert "Initial response" in result
        assert "Final answer" in result

    def test_preserves_normal_content(self):
        response = """This is a normal response.
        
It has multiple paragraphs.
        
All content should be preserved."""

        result = clean_response(response)

        assert "normal response" in result
        assert "multiple paragraphs" in result
        assert "preserved" in result

    def test_handles_empty_response(self):
        result = clean_response("")
        assert result == ""

    def test_handles_response_with_only_tags(self):
        result = clean_response("<system-reminder>mode changed</system-reminder>")
        assert result == ""

    def test_multiple_consecutive_newlines(self):
        response = """Line 1



Line 2




Line 3"""

        result = clean_response(response)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
