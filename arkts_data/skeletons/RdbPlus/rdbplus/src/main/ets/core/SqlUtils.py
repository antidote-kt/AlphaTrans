from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class SqlUtils:
    columns: list[TableFieldParams] = None
    tableName: str = None
    idName: str = None
    propertyKeys: list[str] = None
    fields: list[str] = None
    fieldsTemp: str = None
    valueTemp: str = None

    def __init__(self, tableName: str, columns: list[TableFieldParams]) -> None:
        pass

    def list(self, selectSql: str, whereSql: str, groupSql: str, orderSql: str) -> Any:
        pass

    def getOne(self, selectSql: str, whereSql: str, groupSql: str, orderSql: str) -> Any:
        pass

    def count(self, whereSql: str, groupSql: str, orderSql: str) -> Any:
        pass

    def page(self, selectSql: str, whereSql: str, groupSql: str, orderSql: str, current: float, size: float) -> Any:
        pass

    def getById(self, id: int | float | str | bool | None | bytes) -> Any:
        pass

    def insert(self, obj: T) -> Any:
        pass

    def insertBatch(self, list: list[T]) -> Any:
        pass

    def updateById(self, obj: T) -> Any:
        pass

    def deleteById(self, id: int | float | str | bool | None | bytes) -> Any:
        pass

    def update(self, setSql: str, whereSql: str) -> Any:
        pass

    def delete(self, whereSql: str) -> Any:
        pass
