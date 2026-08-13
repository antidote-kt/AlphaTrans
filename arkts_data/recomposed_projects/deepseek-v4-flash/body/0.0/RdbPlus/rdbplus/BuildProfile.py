from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class BuildProfile:
    HAR_VERSION: Any = None
    BUILD_MODE_NAME: Any = "BUILD_MODE_NAME"
    DEBUG: Any = None
    TARGET_NAME: Any = None
