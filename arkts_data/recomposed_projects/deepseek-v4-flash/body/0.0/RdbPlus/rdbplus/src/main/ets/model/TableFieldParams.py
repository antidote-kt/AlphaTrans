from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class TableFieldParams(ABC):
    name: str = None
    type: FieldType = None
    isPrimaryKey: bool = None
    propertyKey: str = None
