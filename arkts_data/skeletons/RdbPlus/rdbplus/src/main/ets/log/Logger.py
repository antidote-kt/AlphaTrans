from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Logger(ABC):

    @abstractmethod
    def debug(self, *args: str) -> None:
        pass

    @abstractmethod
    def info(self, *args: str) -> None:
        pass

    @abstractmethod
    def warn(self, *args: str) -> None:
        pass

    @abstractmethod
    def error(self, *args: str) -> None:
        pass
