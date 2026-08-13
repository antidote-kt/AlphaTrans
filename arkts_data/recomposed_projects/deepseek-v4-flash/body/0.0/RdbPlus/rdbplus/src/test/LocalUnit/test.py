from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def localUnitTest() -> Any:
    # Defines a test suite.
    a = 'abc'
    b = 'b'
    assert b in a
    assert a == a

test_localUnitTest = localUnitTest
