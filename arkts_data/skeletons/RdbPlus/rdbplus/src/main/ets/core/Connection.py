from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Connection:
    __id: str = None
    __store: relationalStore.RdbStore = None
    __context: Context | None = None
    __logger: Logger | None = None

    @property
    def version(self) -> Any:
        pass

    @version.setter
    def version(self, v: float) -> Any:
        pass

    def getStore(self) -> Any:
        pass

    @staticmethod
    async def deleteRdbStore(dbName: str) -> Awaitable[None]:
        pass

    @staticmethod
    def init(context: Context = None, logger: Logger = None) -> None:
        pass

    def __init__(self, id: str, store: relationalStore.RdbStore) -> None:
        pass

    @staticmethod
    async def create(config: TypedDict('StoreConfig', {'name': str, 'securityLevel': Any})) -> Awaitable[Connection]:
        pass

    async def execDML(self, sql: str, params: list[relationalStore.ValueType] = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        pass

    async def execDQL(self, sql: str, params: list[relationalStore.ValueType] = None) -> Awaitable['relationalStore.ResultSet']:
        pass

    def beginTransaction(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollBack(self) -> None:
        pass

    async def close(self) -> Awaitable[None]:
        pass

    async def backup(self, fileName: str = 'Backup.db') -> Awaitable[None]:
        pass

    async def restore(self, fileName: str = 'Backup.db') -> Awaitable[None]:
        pass
