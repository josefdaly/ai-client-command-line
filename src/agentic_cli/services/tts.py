import subprocess
from typing import Optional


class TTSService:
    def __init__(self, voice: Optional[str] = None, rate: int = 175):
        self.voice = voice or "Victoria"
        self.rate = rate
        self._process: Optional[subprocess.Popen] = None

    @property
    def is_speaking(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def speak(self, text: str) -> bool:
        if not text:
            return True
        self.stop()
        cmd = ["say", "-v", self.voice, "-r", str(self.rate), text]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def speak_async(self, text: str):
        if not text:
            return
        self.stop()
        cmd = ["say", "-v", self.voice, "-r", str(self.rate), text]
        self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        if self._process:
            self._process.terminate()
            self._process = None

    def wait_until_done(self):
        if self._process:
            self._process.wait()
            self._process = None
