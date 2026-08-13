from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.BaseMapper import BaseMapper
from rdbplus.src.main.ets.core.Connection import Connection

class EmpMapper:
    mapper: BaseMapper[Employee] = None

    @staticmethod
    def getInstance() -> Any:
        if EmpMapper.mapper is None:
            config = {'name': 'RdbTest.db', 'securityLevel': 3}
            from types import SimpleNamespace
            params = SimpleNamespace()
            setattr(params, 'class', Employee)
            setattr(params, 'config', config)
            EmpMapper.mapper = BaseMapper.build(params)
        return EmpMapper.mapper

    async def createTable() -> Any:
        db = None
        try:
            db = await EmpMapper.getInstance().getConnection()
            print('createTable 首次打开 版本 0')
            if db.version == 0:
                await db.execDML(
                    'create table if not exists "t_emp" ('
                    'id integer primary key autoincrement, '
                    'name varchar(20)'
                    ')', []
                )
                db.version = 1
                print('createTable 创建表后 版本 1')
            if db.version == 1:
                await db.execDML('ALTER TABLE t_emp ADD COLUMN age integer')
                db.version = 2
                print('createTable 修改后 版本 2')
            if db.version == 2:
                print('createTable 最终版本 2')
        except Exception as e:
            print(e)
        finally:
            if db:
                await db.close()
