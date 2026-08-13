from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def showToast(message: str, time: float = 3000) -> Any:
    pass

def showDialog(msg: str, title: str = '系统提示', callBack: Any = None) -> Any:
    pass

def alertDialog(msg: str, submit: Callable[[], None], title: str = '系统提示') -> Any:
    pass
