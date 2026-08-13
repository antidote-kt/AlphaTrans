from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class BuildParams(ABC):
    class_: Callable[[], T] = None
    config: TypedDict('StoreConfig', {'name': str, 'securityLevel': Any}) = None
