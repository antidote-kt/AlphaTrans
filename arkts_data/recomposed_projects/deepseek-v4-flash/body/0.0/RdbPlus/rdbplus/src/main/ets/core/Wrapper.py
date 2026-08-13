from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Wrapper:
    selectSql: str = '*'
    groupSql: str = None
    havingSql: str = None
    orderList: list[str] = None
    whereList: list[str] = []
    valueList: list[ValueType] = []
    updateList: list[str] = None
    updateValueList: list[ValueType] = []

    def __init__(self) -> None:
        pass

    def set(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Any:
            if condition:
                self.updateList.append(f"{field} = ?")
                self.updateValueList.append(value)
            return self

    def eq(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} = ?")
                self.valueList.append(value)
            return self

    def notEq(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} != ?")
                self.valueList.append(value)
            return self

    def in_(self, field: str, value: list[ValueType], condition: bool = True) -> Wrapper:
            if condition:
                placeholders = ','.join('?' * len(value))
                self.whereList.append(f"and {field} in ({placeholders})")
                self.valueList.extend(value)
            return self

    def notIn(self, field: str, value: list[ValueType], condition: bool = True) -> Wrapper:
            if condition:
                placeholders = ','.join('?' for _ in value)
                self.whereList.append(f"and {field} not in ({placeholders})")
                self.valueList.extend(value)
            return self

    def lt(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} < ?")
                self.valueList.append(value)
            return self

    def lte(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} <= ?")
                self.valueList.append(value)
            return self

    def gt(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} > ?")
                self.valueList.append(value)
            return self

    def gte(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} >= ?")
                self.valueList.append(value)
            return self

    def between(self, field: str, start: int | float | str | bool | None | bytes, end: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} between ? and ?")
                self.valueList.append(start)
                self.valueList.append(end)
            return self

    def notBetween(self, field: str, start: int | float | str | bool | None | bytes, end: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} not between ? and ?")
                self.valueList.append(start)
                self.valueList.append(end)
            return self

    def like(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} like ?")
                self.valueList.append(value)
            return self

    def notLike(self, field: str, value: int | float | str | bool | None | bytes, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} not like ?")
                self.valueList.append(value)
            return self

    def isNull(self, field: str, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} is null")
            return self

    def isNotNull(self, field: str, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append(f"and {field} is not null")
            return self

    def orderByAsc(self, field: str, condition: bool = True) -> Wrapper:
            if condition:
                self.orderList.append(f"{field} asc")
            return self

    def orderByDesc(self, field: str, condition: bool = True) -> Wrapper:
            if condition:
                self.orderList.append(f"{field} desc")
            return self

    def groupBy(self, fields: str | list[str], condition: bool = True) -> Wrapper:
            if condition:
                if isinstance(fields, list):
                    self.groupSql = f"group by {','.join(fields)}"
                else:
                    self.groupSql = f"group by {fields}"
            return self

    def having(self, sql: str, condition: bool = True) -> Wrapper:
            if condition:
                self.havingSql = f"having {sql}"
            return self

    def or_(self, wrapper: Wrapper, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append('or (1=1 ')
                self.whereList.extend(wrapper.whereList)
                self.whereList.append(')')
                self.valueList.extend(wrapper.valueList)
            return self

    def and_(self, wrapper: Wrapper, condition: bool = True) -> Wrapper:
            if condition:
                self.whereList.append('and (1=1 ')
                self.whereList.extend(wrapper.whereList)
                self.whereList.append(')')
                self.valueList.extend(wrapper.valueList)
            return self

    def select(self, *field: str) -> Wrapper:
            self.selectSql = ','.join(field)
            return self

    def selectSQL(self, sql: str) -> Wrapper:
            self.selectSql = sql
            return self
