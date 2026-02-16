import speech_recognition as sr
from typing import Optional


class STTService:
    def __init__(self, language: str = "en-US", phrase_time_limit: float = 10.0):
        self.language = language
        self.phrase_time_limit = phrase_time_limit
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.5
        self.recognizer.phrase_threshold = 0.3
        self.microphone = sr.Microphone()

    def listen(self, timeout: Optional[float] = None) -> Optional[str]:
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )
        except sr.WaitTimeoutError:
            return None
        except OSError as e:
            if "pyzmq" in str(e) or "microphone" in str(e).lower():
                return None
            raise

        try:
            text = self.recognizer.recognize_google(audio, language=self.language)
            return text if text else None
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return None
