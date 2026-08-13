from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.core.Wrapper import Wrapper

class MyWrapper(Wrapper):

    @staticmethod
    def build(parent: Wrapper) -> MyWrapper:
        pass

    def getSelect(self) -> str:
        pass

    def getWhere(self) -> str:
        pass

    def getValue(self) -> list[ValueType]:
        pass

    def getOrder(self) -> str:
        pass

    def getGroup(self) -> str:
        pass

    def getUpdate(self) -> Any:
        pass

    def getUpdateValue(self) -> Any:
        pass
