from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class FieldType(Enum):
    NUMBER = 'NUMBER'
    TEXT = 'TEXT'
    BLOB = 'BLOB'
    BOOLEAN = 'BOOLEAN'
