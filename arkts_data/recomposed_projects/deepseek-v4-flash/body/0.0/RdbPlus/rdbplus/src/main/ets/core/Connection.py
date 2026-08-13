from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.log.Logger import Logger

class Connection:
    id: str = None
    store: relationalStore.RdbStore = None
    context: Context = None
    logger: Logger = None

    @property
    def version(self) -> Any:
        return self.store.version

    def version(self, v: float) -> Any:

        self.store.version = v

    def getStore(self) -> Any:
            return self.store

    @staticmethod
    async def deleteRdbStore(dbName: str) -> Awaitable[None]:
        if Connection.context is None:
            if Connection.logger is not None:
                Connection.logger.error('Connection未初始化，context获取失败')
            return
        relationalStore.deleteRdbStore(Connection.context, dbName)
        if Connection.logger is not None:
            Connection.logger.info('deleteRdbStore success')

    def init(context: Context = None, logger: Logger = None) -> None:

        if context is None:
            if Connection.logger is not None:
                Connection.logger.error('Connection初始化失败，参数异常')
            return
        Connection.context = context
        Connection.logger = logger

    def __init__(self, id: str, store: relationalStore.RdbStore) -> None:
            self.id = id
            self.store = store

    @staticmethod
    async def create(config: TypedDict('StoreConfig', {'name': str, 'securityLevel': Any})) -> Awaitable[Connection]:
        store = await relationalStore.getRdbStore(Connection.context, config)
        db = Connection(str(uuid.uuid4()), store)
        if Connection.logger:
            Connection.logger.info(f"connection create {db.id}")
        return db

    async def execDML(self, sql: str, params: list[relationalStore.ValueType] = None) -> Awaitable[Union[int, float, str, bool, None, bytes]]:
            if params is None:
                params = []
            try:
                if self.logger:
                    self.logger.info('execDML:', sql, json.dumps(params))
                return await self.store.execute(sql, params)
            except Exception as e:
                if self.logger:
                    self.logger.error('execDML', str(e), '', json.dumps(e.__dict__ if hasattr(e, '__dict__') else str(e)))
                raise Exception('execDML 执行失败')

    async def execDQL(self, sql: str, params: list[relationalStore.ValueType] = None) -> Awaitable['relationalStore.ResultSet']:
            if params is None:
                params = []
            try:
                if self.logger:
                    self.logger.info('execDQL:', sql, json.dumps(params))
                return await self.store.querySql(sql, params)
            except Exception as e:
                if self.logger:
                    self.logger.error('execDQL', str(e), str(getattr(e, 'code', '')), json.dumps(str(e)))
                raise Exception('execDQL 执行失败')

    def beginTransaction(self) -> None:
            if self.logger is not None:
                self.logger.info('transaction begin ', self.id)
            self.store.beginTransaction()

    def commit(self) -> None:
            if self.logger is not None:
                self.logger.info('transaction commit ', self.id)
            self.store.commit()

    def rollBack(self) -> None:
            if self.logger is not None:
                self.logger.info('transaction rollBack ', self.id)
            self.store.rollBack()

    async def close(self) -> Awaitable[None]:
            if self.logger is not None:
                self.logger.info('connection close ', self.id)
            self.store.close()

    async def backup(self, fileName: str = 'Backup.db') -> Awaitable[None]:
            self.store.backup(fileName)
            if self.logger is not None:
                self.logger.info('backup success')

    async def restore(self, fileName: str = 'Backup.db') -> Awaitable[None]:
            self.store.restore(fileName)
            if Connection.logger is not None:
                Connection.logger.info('restore success')
