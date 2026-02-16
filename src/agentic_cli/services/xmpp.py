import os
import asyncio
import ssl
import sys
import threading
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Only apply macOS Python 3.12 fix
if sys.platform == "darwin" and sys.version_info >= (3, 12):
    import backports.ssl_match_hostname

    ssl.match_hostname = backports.ssl_match_hostname.match_hostname

import aioxmpp
from aioxmpp import JID
from aioxmpp import Message
from aioxmpp import PresenceManagedClient
from aioxmpp.security_layer import make

from .base import Service


class XMPPService(Service):
    def __init__(self, env_file: Optional[Path] = None):
        self.env_file = env_file or Path(".env")
        self._load_config()

    def _load_config(self):
        if self.env_file.exists():
            load_dotenv(self.env_file)

        self.jid = os.getenv("XMPP_JID")
        self.password = os.getenv("XMPP_PASSWORD")

        if not self.jid or not self.password:
            raise ValueError("XMPP_JID and XMPP_PASSWORD must be set in .env file")

    @property
    def name(self) -> str:
        return "xmpp"

    def initialize(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def send(
        self, recipient: str, message: str, attachment_content: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        result = [None]
        error = [None]

        full_message = message
        if attachment_content:
            full_message = f"{message}\n\n--- Attachment ---\n{attachment_content}"

        def run_xmpp():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    jid = JID.fromstr(self.jid)
                    security_layer = make(password_provider=self.password, no_verify=True)
                    client = PresenceManagedClient(jid, security_layer)

                    msg = Message(type_=aioxmpp.MessageType.CHAT)
                    msg.to = JID.fromstr(recipient)
                    msg.body[None] = full_message

                    async def send_msg():
                        async with asyncio.timeout(15):
                            async with client.connected():
                                await client.send(msg)

                    loop.run_until_complete(send_msg())
                    result[0] = True
                finally:
                    loop.close()

            except Exception as e:
                error[0] = f"{type(e).__name__}: {e}"

        thread = threading.Thread(target=run_xmpp)
        thread.start()
        thread.join()

        if result[0]:
            return True, None
        else:
            return False, error[0] or "Unknown error"
