from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Employee:
    id: float | None = None
    name: str | None = None
    age: float | None = None
