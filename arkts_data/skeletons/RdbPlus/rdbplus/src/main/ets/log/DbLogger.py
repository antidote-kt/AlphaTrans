from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.log.Logger import Logger

class DbLogger(Logger):

    def debug(self, *args: str) -> None:
        pass

    def info(self, *args: str) -> None:
        pass

    def warn(self, *args: str) -> None:
        pass

    def error(self, *args: str) -> None:
        pass
