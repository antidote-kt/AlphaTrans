from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def getEntityMeta(Type: Type[Any]) -> str:
    meta = getattr(Type, '__tableMeta__', None)
    if meta is not None:
        table_name = getattr(meta, 'tableName', None)
        if table_name is not None:
            return table_name
    return ''

def getColumnMeta(Type: Type[Any]) -> list[TableFieldParams]:
    meta = getattr(Type, '__tableFieldMeta__', None)
    return meta if meta is not None else []
