from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class EntryAbility:

    def onCreate(self, want: dict[str, Any], launchParam: AbilityConstant.LaunchParam) -> None:
        pass

    def onWindowStageCreate(self, windowStage: window.WindowStage) -> Any:
        pass
