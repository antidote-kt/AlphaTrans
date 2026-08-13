from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

class Index:
    mapper: Any = None

    def __init__(self, value: Index = None, storage: LocalStorage = None) -> None:
            self.value = value
            self.storage = storage

    def build(self) -> Any:
            class Button:
                def __init__(self, text, onClick):
                    self.text = text
                    self.onClick = onClick

            class Divider:
                def __init__(self, width='100%', height=20, color='#000'):
                    self.width = width
                    self.height = height
                    self.color = color

            class Flex:
                def __init__(self, children, width='100%', height='100%', wrap=None):
                    self.children = children
                    self.width = width
                    self.height = height
                    self.wrap = wrap

            children = []

            # 删除数据库
            async def on_delete_db(event=None):
                Connection.deleteRdbStore('RdbTest.db')
                showDialog('删除数据库')
            children.append(Button('删除数据库', on_delete_db))

            # 初始化
            async def on_init(event=None):
                try:
                    await EmpMapper.createTable()
                    showDialog('初始化完成，查看日志')
                except Exception as e:
                    console.error(e)
            children.append(Button('初始化', on_init))

            # count
            async def on_count(event=None):
                try:
                    num = await self.mapper.count(Wrapper())
                    showDialog(str(num))
                except Exception as e:
                    console.error(e)
            children.append(Button('count', on_count))

            # page
            async def on_page(event=None):
                try:
                    page = await self.mapper.getPage(1, 10, Wrapper())
                    # 总数
                    total = page.total
                    # 当前页
                    current = page.current
                    # 每页条数
                    size = page.size
                    # 结果集
                    record = page.record
                    showDialog(str(page))
                except Exception as e:
                    console.error(e)
            children.append(Button('page', on_page))

            # getObject name=123
            async def on_get_object(event=None):
                try:
                    res = await self.mapper.getObject(Wrapper().eq('name', '123'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('getObject name=123', on_get_object))

            # getObjectBySql count(*)
            async def on_get_object_by_sql(event=None):
                try:
                    res = await self.mapper.getObjectBySql('select count(*) from t_emp', [])
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('getObjectBySql count(*)', on_get_object_by_sql))

            # getById(3)
            async def on_get_by_id(event=None):
                try:
                    res = await self.mapper.getById(3)
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('getById(3)', on_get_by_id))

            # getList(name=123)
            async def on_get_list_eq(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().eq('name', '123'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('getList(name=123)', on_get_list_eq))

            # getList(name!==123)
            async def on_get_list_not_eq(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().notEq('name', '123'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('getList(name!==123)', on_get_list_not_eq))

            # in[123 124]
            async def on_in(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().in_('name', ['123', '124']))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('in[123 124]', on_in))

            # notIn[123 124]
            async def on_not_in(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().notIn('name', ['123', '124']))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('notIn[123 124]', on_not_in))

            # lt(id<2)
            async def on_lt(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().lt('id', 2))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('lt(id<2)', on_lt))

            # lte(id<=2)
            async def on_lte(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().lte('id', 2))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('lte(id<=2)', on_lte))

            # gt(id>2)
            async def on_gt(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().gt('id', 2))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('gt(id>2)', on_gt))

            # gte(id>=2)
            async def on_gte(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().gte('id', 2))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('gte(id>=2)', on_gte))

            # between id[2 4]
            async def on_between(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().between('id', 2, 4))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('between id[2 4]', on_between))

            # notBetween id[2 4]
            async def on_not_between(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().notBetween('id', 2, 4))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('notBetween id[2 4]', on_not_between))

            # Divider
            children.append(Divider())

            # like name(12%)
            async def on_like(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().like('name', '12%'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('like name(12%)', on_like))

            # notLike name(12%)
            async def on_not_like(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().notLike('name', '12%'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('notLike name(12%)', on_not_like))

            # isNull(name)
            async def on_is_null(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().isNull('name'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('isNull(name)', on_is_null))

            # isNotNull(name)
            async def on_is_not_null(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().isNotNull('name'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('isNotNull(name)', on_is_not_null))

            # orderByAsc(id)
            async def on_order_asc(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().orderByAsc('id'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('orderByAsc(id)', on_order_asc))

            # orderByDesc(id)
            async def on_order_desc(event=None):
                try:
                    res = await self.mapper.getList(Wrapper().orderByDesc('id'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('orderByDesc(id)', on_order_desc))

            # Divider
            children.append(Divider())

            # groupBy age=18 count(*)
            async def on_group_by(event=None):
                try:
                    res = await self.mapper.getObject(Wrapper().groupBy('age').select('age', 'count(*)'))
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('groupBy age=18 count(*)', on_group_by))

            # having age!=30 count(*)
            async def on_having(event=None):
                try:
                    res = await self.mapper.getObject(
                        Wrapper().select('age', 'count(*)').groupBy('age').having('age != 30')
                    )
                    showDialog(str(res))
                except Exception as e:
                    console.error(e)
            children.append(Button('having age!=30 count(*)', on_having))

            # Divider
            children.append(Divider())

            # 批量添加8条
            async def on_batch_insert(event=None):
                try:
                    emp = [
                        Employee(name='123', myAge=18),
                        Employee(name='124', myAge=18),
                        Employee(name='张三', myAge=20),
                        Employee(name='李四', myAge=20),
                        Employee(name='网二', myAge=21),
                        Employee(name=None, myAge=None),
                        Employee(name='age是undefined', myAge=None),
                        Employee(name=None, myAge=30),
                    ]
                    num = await self.mapper.insertBatch(emp)
                    showDialog('成功' + str(num))
                except Exception as e:
                    console.error(e)
            children.append(Button('批量添加8条', on_batch_insert))

            # 首次updateById(3)
            async def on_update_by_id(event=None):
                try:
                    emp = Employee()
                    emp.id = 3
                    emp.name = 'updateById'
                    num = await self.mapper.updateById(emp)
                    showDialog('成功' + str(num))
                except Exception as e:
                    console.error(e)
            children.append(Button('首次updateById(3)', on_update_by_id))

            # 再次修改update
            async def on_update(event=None):
                try:
                    num = await self.mapper.update(
                        Wrapper().set('name', 'update使用set修改').set('id', 100).eq('name', 'updateById')
                    )
                    showDialog('成功' + str(num))
                except Exception as e:
                    console.error(e)
            children.append(Button('再次修改update', on_update))

            # 删除id=3
            async def on_delete(event=None):
                try:
                    num = await self.mapper.delete(Wrapper().eq('id', 3))
                    showDialog('成功' + str(num))
                except Exception as e:
                    console.error(e)
            children.append(Button('删除id=3', on_delete))

            # deleteById id=3
            async def on_delete_by_id(event=None):
                try:
                    num = await self.mapper.deleteById(3)
                    showDialog('成功' + str(num))
                except Exception as e:
                    console.error(e)
            children.append(Button('deleteById id=3', on_delete_by_id))

            # Divider
            children.append(Divider())

            # 事务成功
            async def on_tx_success(event=None):
                try:
                    db = await self.mapper.getConnection()
                    try:
                        db.beginTransaction()
                        emp = Employee()
                        emp.name = '事务'
                        emp.myAge = 44
                        num = await self.mapper.insert(emp, db)
                        db.commit()
                        showDialog('成功' + str(num))
                    except Exception:
                        db.rollBack()
                    finally:
                        db.close()
                except Exception:
                    print('db获取失败')
            children.append(Button('事务成功', on_tx_success))

            # 事务失败
            async def on_tx_fail(event=None):
                try:
                    db = await self.mapper.getConnection()
                    try:
                        db.beginTransaction()
                        emp = Employee()
                        emp.name = '事务失败'
                        await self.mapper.insert(emp, db)
                        raise Exception('我的异常,事务失败')
                    except Exception as e:
                        db.rollBack()
                        console.error(e)
                    finally:
                        db.close()
                except Exception:
                    print('db获取失败')
            children.append(Button('事务失败', on_tx_fail))

            return Flex(children, width='100%', height='100%', wrap=True)
