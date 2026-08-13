from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.core.SqlUtils import SqlUtils
from rdbplus.src.main.ets.core.DecoratorUtils import getColumnMeta
from rdbplus.src.main.ets.core.DecoratorUtils import getEntityMeta
from rdbplus.src.main.ets.core.Connection import Connection
from rdbplus.src.main.ets.core.MyWrapper import MyWrapper
from rdbplus.src.main.ets.core.Wrapper import Wrapper
from rdbplus.src.main.ets.model.Page import Page

class BaseMapper:
    config: TypedDict('StoreConfig', {'name': str, 'securityLevel': Any}) = None
    sqlUtils: SqlUtils[T] = None
    getRow: Callable[[relationalStore.ResultSet], T] = None

    def build(param: BuildParams[T]) -> BaseMapper[T]:
        # 'class' is a keyword, so use getattr to access the entity class
        entity_class = getattr(param, 'class')
        table_name = getEntityMeta(entity_class)
        columns_meta = getColumnMeta(entity_class)

        if not table_name or not columns_meta:
            print('rdb BaseMapper build 失败，实体类缺少装饰器')
            raise ValueError('实体类缺少装饰器')

        def get_row(res: relationalStore.ResultSet) -> T:
            obj = entity_class()
            for col in columns_meta:
                name = col.name or ''
                property_key = col.propertyKey or ''
                index = res.getColumnIndex(name)
                if index != -1:
                    setattr(obj, property_key, res.getValue(index))
            return obj

        sql_utils = SqlUtils(table_name, columns_meta)
        return BaseMapper(param.config, sql_utils, get_row)

    def __init__(self, config: TypedDict('StoreConfig', {'name': str, 'securityLevel': Any}), sqlUtils: SqlUtils[T], getRow: Callable[[relationalStore.ResultSet], T]) -> None:
            self.config = config
            self.sqlUtils = sqlUtils
            self.getRow = getRow

    async def getConnection(self) -> Awaitable[Connection]:
            return await Connection.create(self.config)

    async def count(self, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[float]:
            if wrapper is None:
                wrapper = Wrapper()
            is_close = True
            if db is None:
                db = await self.getConnection()
            else:
                is_close = False

            my_wrapper = MyWrapper.build(wrapper)
            sql = self.sqlUtils.count(
                my_wrapper.getWhere(),
                my_wrapper.getGroup(),
                my_wrapper.getOrder()
            )

            res = await db.execDQL(sql, my_wrapper.getValue())
            try:
                res.goToFirstRow()
                count = res.getLong(0)
            finally:
                res.close()
                if is_close:
                    await db.close()

            return count

    async def getObject(self, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[List[Any]]:
            is_close = True
            if db is None:
                db = await self.getConnection()
            else:
                is_close = False
            if wrapper is None:
                wrapper = Wrapper()
            my_wrapper = MyWrapper.build(wrapper)
            sql = self.sqlUtils.list(my_wrapper.getSelect(), my_wrapper.getWhere(), my_wrapper.getGroup(), my_wrapper.getOrder())
            res = await db.execDQL(sql, my_wrapper.getValue())
            column_names = res.columnNames
            result_list = []
            while res.goToNextRow():
                obj = {}
                for name in column_names:
                    obj[name] = res.getValue(res.getColumnIndex(name))
                result_list.append(obj)
            res.close()
            if is_close:
                await db.close()
            return result_list

    async def getObjectBySql(self, sql: str, params: list[ValueType], db: Connection = None) -> Awaitable[List[Any]]:
            is_close = True
            if db is None:
                db = await self.getConnection()
            else:
                is_close = False
            res = await db.execDQL(sql, params)
            column_names = res.columnNames
            result_list = []
            while res.goToNextRow():
                obj = {}
                for name in column_names:
                    obj[name] = res.getValue(res.getColumnIndex(name))
                result_list.append(obj)
            res.close()
            if is_close:
                await db.close()
            return result_list

    async def getList(self, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[list[T]]:
            is_close = True
            if db is None:
                db = await self.getConnection()
            else:
                is_close = False
            if wrapper is None:
                wrapper = Wrapper()
            my_wrapper = MyWrapper.build(wrapper)
            sql = self.sqlUtils.list(my_wrapper.getSelect(), my_wrapper.getWhere(), my_wrapper.getGroup(), my_wrapper.getOrder())
            res = await db.execDQL(sql, my_wrapper.getValue())
            result_list = []
            while res.goToNextRow():
                obj = self.getRow(res)
                result_list.append(obj)
            res.close()
            if is_close:
                await db.close()
            return result_list

    async def getOne(self, wrapper: Wrapper = None, db: Connection = None) -> Promise[T | undefined]:
        isClose = True
        if wrapper is None:
            wrapper = Wrapper()
        if db is None:
            db = await self.getConnection()
        else:
            isClose = False
        myWrapper = MyWrapper.build(wrapper)
        sql = self.sqlUtils.getOne(myWrapper.getSelect(), myWrapper.getWhere(), myWrapper.getGroup(), myWrapper.getOrder())
        res = await db.execDQL(sql, myWrapper.getValue())
        one = None
        if res.goToNextRow():
            one = self.getRow(res)
        res.close()
        if isClose:
            await db.close()
        return one

    async def getPage(self, current: float, size: float, wrapper: Wrapper = None, db: Connection = None) -> Awaitable[Page[T]]:
            is_close = True
            if wrapper is None:
                wrapper = Wrapper()
            if db is None:
                db = await self.getConnection()
            else:
                is_close = False
            count = await self.count(wrapper, db)
            my_wrapper = MyWrapper.build(wrapper)
            sql = self.sqlUtils.page(
                my_wrapper.getSelect(),
                my_wrapper.getWhere(),
                my_wrapper.getGroup(),
                my_wrapper.getOrder(),
                current,
                size
            )
            res = await db.execDQL(sql, my_wrapper.getValue())
            list_t = []
            while res.goToNextRow():
                list_t.append(self.getRow(res))
            res.close()
            if is_close:
                await db.close()
            return Page(count, current, size, list_t)

    async def getById(self, id: int | float | str | bool | None | bytes, db: Connection = None) -> Promise[T | undefined]:
            isClose = True
            if db is None:
                db = await self.getConnection()
            else:
                isClose = False
            sql_data = self.sqlUtils.getById(id)
            sql = sql_data["sql"]
            values = sql_data["values"]
            res = await db.execDQL(sql, values)
            entity = None
            if res.goToFirstRow():
                entity = self.getRow(res)
            res.close()
            if isClose:
                await db.close()
            return entity

    async def insert(self, obj: T, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        is_close = True
        if db is None:
            db = await self.getConnection()
        else:
            is_close = False
        sql_data = self.sqlUtils.insert(obj)
        res = await db.execDML(sql_data["sql"], sql_data["values"])
        if is_close:
            await db.close()
        return res

    async def insertBatch(self, list: list[T], db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        isClose = True
        if db is None:
            db = await self.getConnection()
        else:
            isClose = False
        sqlData = self.sqlUtils.insertBatch(list)
        res = await db.execDML(sqlData["sql"], sqlData["values"])
        if isClose:
            await db.close()
        return res

    async def update(self, wrapper: Wrapper, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
            is_close = True
            if db is None:
                db = await self.getConnection()
            else:
                is_close = False
            my_wrapper = MyWrapper.build(wrapper)
            sql = self.sqlUtils.update(my_wrapper.getUpdate(), my_wrapper.getWhere())
            params = my_wrapper.getUpdateValue() + my_wrapper.getValue()
            res = await db.execDML(sql, params)
            if is_close:
                await db.close()
            return res

    async def updateById(self, obj: T, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
        isClose = True
        if db is None:
            db = await self.getConnection()
        else:
            isClose = False
        sqlData = self.sqlUtils.updateById(obj)
        res = await db.execDML(sqlData["sql"], sqlData["values"])
        if isClose:
            await db.close()
        return res

    async def delete(self, wrapper: Wrapper, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
            isClose = True
            if db is None:
                db = await self.getConnection()
            else:
                isClose = False
            myWrapper = MyWrapper.build(wrapper)
            sql = self.sqlUtils.delete(myWrapper.getWhere())
            res = await db.execDML(sql, myWrapper.getValue())
            if isClose:
                await db.close()
            return res

    async def deleteById(self, id: int | float | str | bool | None | bytes, db: Connection = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
            is_close = True
            if db is None:
                db = await self.getConnection()
            else:
                is_close = False
            sql_data = self.sqlUtils.deleteById(id)
            res = await db.execDML(sql_data["sql"], sql_data["values"])
            if is_close:
                await db.close()
            return res
