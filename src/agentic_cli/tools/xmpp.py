from pathlib import Path
from typing import Optional

from .base import Tool, ToolResult
from ..services.xmpp import XMPPService


class XMPPTool(Tool):
    def __init__(self, env_file: Optional[Path] = None):
        self._service: Optional[XMPPService] = None
        self.env_file = env_file

    def _get_service(self) -> XMPPService:
        if self._service is None:
            self._service = XMPPService(self.env_file)
            if not self._service.initialize():
                raise RuntimeError("Failed to initialize XMPP service")
        return self._service

    @property
    def name(self) -> str:
        return "xmpp"

    @property
    def description(self) -> str:
        return "Send XMPP (Jabber) messages to a recipient. Requires recipient JID and message content. Optionally attach a file by providing the file path."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "The JID (Jabber ID) to send the message to",
                },
                "message": {
                    "type": "string",
                    "description": "The message content to send",
                },
                "attachment": {
                    "type": "string",
                    "description": "Optional path to a file to attach to the message",
                },
            },
            "required": ["recipient", "message"],
        }

    def execute(self, recipient: str, message: str, attachment: Optional[str] = None) -> ToolResult:
        try:
            service = self._get_service()

            attachment_content = None
            if attachment:
                path = Path(attachment)
                if path.exists():
                    attachment_content = path.read_text()
                else:
                    return ToolResult(
                        success=False, result=None, error=f"Attachment file not found: {attachment}"
                    )

            success, error = service.send(recipient, message, attachment_content)

            if success:
                result_msg = f"Message sent to {recipient}: {message[:50]}..."
                if attachment:
                    result_msg += f" (with attachment: {attachment})"
                return ToolResult(success=True, result=result_msg)
            else:
                return ToolResult(
                    success=False, result=None, error=error or "Failed to send message"
                )

        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
