from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Index:
    mapper: Any = None

    def __init__(self, value: Index = None, storage: LocalStorage = None) -> None:
        pass

    def build(self) -> Any:
        pass
