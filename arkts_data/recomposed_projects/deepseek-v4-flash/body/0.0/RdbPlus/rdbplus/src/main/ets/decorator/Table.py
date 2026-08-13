from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def Table(options: TableParams) -> Any:
    def decorator(target: Any) -> Any:
        target.__tableMeta__ = options
        return target
    return decorator
