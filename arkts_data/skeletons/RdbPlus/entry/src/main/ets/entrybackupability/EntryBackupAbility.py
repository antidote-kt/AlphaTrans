from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class EntryBackupAbility:

    async def onBackup(self) -> Any:
        pass

    async def onRestore(self, bundleVersion: TypedDict('BundleVersion', {'name': str})) -> Any:
        pass
