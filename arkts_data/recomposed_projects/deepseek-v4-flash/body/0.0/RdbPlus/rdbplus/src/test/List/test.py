from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.test.LocalUnit.test import localUnitTest

def testsuite() -> Any:
    localUnitTest()
