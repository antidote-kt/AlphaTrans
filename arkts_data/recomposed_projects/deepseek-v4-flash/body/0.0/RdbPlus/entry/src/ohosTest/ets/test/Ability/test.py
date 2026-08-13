from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def abilityTest() -> Any:
    # beforeAll no-op
    # beforeEach no-op
    a = 'abc'
    b = 'b'
    assert b in a, "assertContain failed"
    assert a == a, "assertEqual failed"

test_abilityTest = abilityTest
