from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def getEntityMeta(Type: Type[Any]) -> str:
    pass

def getColumnMeta(Type: Type[Any]) -> list[TableFieldParams]:
    pass
