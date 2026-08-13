from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class BaseMapper:
    __config: TypedDict('StoreConfig', {'name': str, 'securityLevel': Any}) = None
    __sqlUtils: SqlUtils[T] = None
    __getRow: Callable[[relationalStore.ResultSet], T] = None

    @staticmethod
    def build(param: BuildParams[T]) -> BaseMapper[T]:
        pass

    def __init__(self, config: TypedDict('StoreConfig', {'name': str, 'securityLevel': Any}), sqlUtils: SqlUtils[T], getRow: Callable[[relationalStore.ResultSet], T]) -> None:
        pass

    async def getConnection(self) -> Awaitable[Connection]:
        pass

    async def count(self, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[float]:
        pass

    async def getObject(self, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[List[Any]]:
        pass

    async def getObjectBySql(self, sql: str, params: list[ValueType], db: Connection = None) -> Awaitable[List[Any]]:
        pass

    async def getList(self, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[list[T]]:
        pass

    async def getOne(self, wrapper: Wrapper = None, db: Connection = None) -> Promise[T | undefined]:
        pass

    async def getPage(self, current: float, size: float, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[Page[T]]:
        pass

    async def getById(self, id: int | float | str | bool | None | bytes, db: Connection = None) -> Promise[T | undefined]:
        pass

    async def insert(self, obj: T, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        pass

    async def insertBatch(self, list: list[T], db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        pass

    async def update(self, wrapper: Wrapper, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        pass

    async def updateById(self, obj: T, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        pass

    async def delete(self, wrapper: Wrapper, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        pass

    async def deleteById(self, id: int | float | str | bool | None | bytes, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        pass
