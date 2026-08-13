from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.ohosTest.ets.test.Ability.test import abilityTest

def testsuite() -> Any:
    def abilityTest() -> Any:
        a = 'abc'
        b = 'b'
        assert b in a, f"Expected '{a}' to contain '{b}'"
        assert a == a, f"Expected '{a}' to equal itself"
    abilityTest()
