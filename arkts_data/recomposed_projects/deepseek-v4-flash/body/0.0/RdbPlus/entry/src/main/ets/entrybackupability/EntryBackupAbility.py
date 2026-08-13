from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class EntryBackupAbility:
    async def onBackup(self) -> Any:
            print("onBackup ok")

    async def onRestore(self, bundleVersion: TypedDict('BundleVersion', {'name': str})) -> Any:
        import json
        import asyncio
        print(f"onRestore ok {json.dumps(bundleVersion)}")
        await asyncio.sleep(0)
        return None
