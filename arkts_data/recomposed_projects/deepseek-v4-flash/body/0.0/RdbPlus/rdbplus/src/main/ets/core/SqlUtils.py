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
            self.columns = columns
            self.tableName = tableName
            self.fields = []
            self.propertyKeys = []
            for column in columns:
                if column.isPrimaryKey:
                    self.idName = column.name
                self.fields.append(column.name)
                self.propertyKeys.append(column.propertyKey)
            self.fieldsTemp = ','.join(self.fields)
            self.valueTemp = ','.join(['?'] * len(self.fields))

    def list(self, selectSql: str, whereSql: str, groupSql: str, orderSql: str) -> Any:
            sql = f"select {selectSql} from {self.tableName} where {whereSql} {groupSql} {orderSql} ;"
            return sql

    def getOne(self, selectSql: str, whereSql: str, groupSql: str, orderSql: str) -> Any:
            sql = f"select {selectSql} from {self.tableName} where {whereSql} {groupSql} {orderSql} limit 1 ;"
            return sql

    def count(self, whereSql: str, groupSql: str, orderSql: str) -> Any:
            sql = f"select count(*) from {self.tableName} where {whereSql} {groupSql} {orderSql};"
            return sql

    def page(self, selectSql: str, whereSql: str, groupSql: str, orderSql: str, current: float, size: float) -> Any:
        offset = int((current - 1) * size)
        limit = int(size)
        sql = f"select {selectSql} from {self.tableName} where {whereSql} {groupSql} {orderSql} limit {offset},{limit};"
        return sql

    def getById(self, id: int | float | str | bool | None | bytes) -> Any:
            sql = f"select * from {self.tableName} where {self.idName} = ?;"
            return {"sql": sql, "values": [id]}

    def insert(self, obj: T) -> Any:
            values = []
            for property_key in self.propertyKeys:
                values.append(getattr(obj, property_key, None))
            sql = f"INSERT INTO {self.tableName} ({self.fieldsTemp}) VALUES ({self.valueTemp});"
            return {"sql": sql, "values": values}

    def insertBatch(self, list: list[T]) -> Any:
            values = []
            for item in list:
                for key in self.propertyKeys:
                    values.append(item.get(key) if isinstance(item, dict) else getattr(item, key, None))
            insert_sql = f"({self.valueTemp})"
            insert_batch_sql = ",".join([insert_sql] * len(list))
            sql = f"INSERT INTO {self.tableName} ({self.fieldsTemp}) VALUES {insert_batch_sql};"
            return {"sql": sql, "values": values}

    def updateById(self, obj: T) -> Any:
            keyValue = obj[self.idName]
            values = []
            set_sql = []
            for i, prop in enumerate(self.propertyKeys):
                if prop in obj:
                    v = obj[prop]
                    set_sql.append(f"{self.fields[i]}=?")
                    values.append(v)
            values.append(keyValue)
            sql = f"update {self.tableName} set {','.join(set_sql)} where {self.idName} = ?;"
            return {"sql": sql, "values": values}

    def deleteById(self, id: int | float | str | bool | None | bytes) -> Any:
            sql = f"delete from {self.tableName} where {self.idName} = ?;"
            return {"sql": sql, "values": [id]}

    def update(self, setSql: str, whereSql: str) -> Any:
            sql = f"update {self.tableName} set {setSql} where {whereSql};"
            return sql

    def delete(self, whereSql: str) -> Any:
        sql = f"delete from {self.tableName} where {whereSql};"
        return sql
