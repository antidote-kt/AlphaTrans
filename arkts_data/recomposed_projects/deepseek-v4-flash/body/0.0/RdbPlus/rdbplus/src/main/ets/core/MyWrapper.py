from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.core.Wrapper import Wrapper

class MyWrapper(Wrapper):
    @staticmethod
    def build(parent: Wrapper) -> MyWrapper:
        my_wrapper = MyWrapper()
        my_wrapper.selectSql = parent.selectSql
        my_wrapper.groupSql = parent.groupSql
        my_wrapper.havingSql = parent.havingSql
        my_wrapper.orderList = parent.orderList
        my_wrapper.whereList = parent.whereList
        my_wrapper.valueList = parent.valueList
        my_wrapper.updateList = parent.updateList
        my_wrapper.updateValueList = parent.updateValueList
        return my_wrapper

    def getSelect(self) -> str:
            return self.selectSql

    def getWhere(self) -> str:
            sql = '1=1 ' + ' '.join(self.whereList)
            return sql

    def getValue(self) -> list[ValueType]:
            return self.valueList

    def getOrder(self) -> str:
            if len(self.orderList) == 0:
                return ''
            else:
                return 'order by ' + ','.join(self.orderList)

    def getGroup(self) -> str:
            if self.groupSql == '':
                return ''
            else:
                sql = self.groupSql
                if self.havingSql != '':
                    sql += f' {self.havingSql}'
                return sql

    def getUpdate(self) -> Any:
            return ", ".join(self.updateList)

    def getUpdateValue(self) -> Any:
            return self.updateValueList
