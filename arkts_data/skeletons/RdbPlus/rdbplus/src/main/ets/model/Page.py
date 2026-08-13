from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Page:
    total: float = None
    current: float = None
    size: float = None
    record: list[T] = None

    def __init__(self, total: float, current: float, size: float, record: list[T]) -> None:
        pass
