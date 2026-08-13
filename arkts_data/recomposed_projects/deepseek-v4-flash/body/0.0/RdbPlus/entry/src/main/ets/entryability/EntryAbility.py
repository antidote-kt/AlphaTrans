from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.core.Connection import Connection

class EntryAbility:
    def onCreate(self, want: dict[str, Any], launchParam: AbilityConstant.LaunchParam) -> None:
            Connection.init(self.context, DbLogger())

    def onWindowStageCreate(self, windowStage: window.WindowStage) -> Any:
        windowStage.loadContent('pages/Index', lambda err: None)
