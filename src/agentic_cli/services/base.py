from abc import ABC, abstractmethod
from typing import Any, Optional


class Service(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass
