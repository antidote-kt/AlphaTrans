from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def abilityTest() -> Any:
    # beforeAll: no preset action
    # beforeEach: no preset action
    a = 'abc'
    b = 'b'
    # assertion for containment
    assert b in a, f"Expected '{a}' to contain '{b}'"
    # assertion for equality
    assert a == a, f"Expected '{a}' to equal itself"

test_abilityTest = abilityTest
