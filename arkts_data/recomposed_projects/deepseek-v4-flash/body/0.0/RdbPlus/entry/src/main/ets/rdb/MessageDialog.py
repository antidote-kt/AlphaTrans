from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def showToast(message: str, time: float = 3000) -> Any:
    # Simulate toast display by printing the message to the console
    print(message)
    return None

def showDialog(msg: str, title: str = '系统提示', callBack: Any = None) -> Any:
    # Simulate showing a dialog with title and message
    print(f"Showing dialog: {title} - {msg}")
    # Since there is no confirm button, simulate cancellation and invoke callback
    if callBack is not None:
        callBack()
    return None

def alertDialog(msg: str, submit: Callable[[], None], title: str = '系统提示') -> Any:
    print(title)
    print(msg)
    if input("请选择: 1-确定, 2-取消: ").strip() == '1':
        submit()
