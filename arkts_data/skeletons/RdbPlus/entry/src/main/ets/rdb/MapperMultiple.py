from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class MapperMultiple:
    __mapper1: BaseMapper[Employee] = None
    __mapper2: BaseMapper[Employee] = None

    @staticmethod
    def getInstance1DB() -> Any:
        pass

    @staticmethod
    def getInstance2DB() -> Any:
        pass
