from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class EmpMapper:
    __mapper: BaseMapper[Employee] = None

    @staticmethod
    def getInstance() -> Any:
        pass

    @staticmethod
    async def createTable() -> Any:
        pass
