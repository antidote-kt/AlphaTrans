from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Page:
    total: float = None
    current: float = 1
    size: float = 10
    record: list[T] = []

    def __init__(self, total: float, current: float, size: float, record: list[T]) -> None:
        self.total = total
        self.current = current
        self.size = size
        self.record = record
