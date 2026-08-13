from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def copyInstance(target: Any, sources: Any) -> T:
    if hasattr(target, 'update') and hasattr(sources, 'items'):
        target.update(sources)
    else:
        for key, value in vars(sources).items():
            setattr(target, key, value)
    return target
