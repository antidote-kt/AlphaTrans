from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Wrapper:
    _selectSql: str = None
    _groupSql: str = None
    _havingSql: str = None
    _orderList: list[str] = None
    _whereList: list[str] = None
    _valueList: list[ValueType] = None
    _updateList: list[str] = None
    _updateValueList: list[ValueType] = None

    def __init__(self) -> None:
        pass

    def set(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Any:
        pass

    def eq(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def notEq(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def in_(self, field: str, value: list[ValueType], condition: bool = True) -> Wrapper:
        pass

    def notIn(self, field: str, value: list[ValueType], condition: bool = True) -> Wrapper:
        pass

    def lt(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def lte(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def gt(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def gte(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def between(self, field: str, start: int | float | str | bool | None | bytes, end: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def notBetween(self, field: str, start: int | float | str | bool | None | bytes, end: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def like(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def notLike(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
        pass

    def isNull(self, field: str, condition: bool = True) -> Wrapper:
        pass

    def isNotNull(self, field: str, condition: bool = True) -> Wrapper:
        pass

    def orderByAsc(self, field: str, condition: bool = True) -> Wrapper:
        pass

    def orderByDesc(self, field: str, condition: bool = True) -> Wrapper:
        pass

    def groupBy(self, fields: str | list[str], condition: bool = True) -> Wrapper:
        pass

    def having(self, sql: str, condition: bool = True) -> Wrapper:
        pass

    def or_(self, wrapper: Wrapper, condition: bool = True) -> Wrapper:
        pass

    def and_(self, wrapper: Wrapper, condition: bool = True) -> Wrapper:
        pass

    def select(self, *field: str) -> Wrapper:
        pass

    def selectSQL(self, sql: str) -> Wrapper:
        pass
