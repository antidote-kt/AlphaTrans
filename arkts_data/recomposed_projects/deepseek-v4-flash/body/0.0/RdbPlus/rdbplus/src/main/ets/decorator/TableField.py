from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *

def TableField(options: TableFieldParams) -> Any:
    class TableFieldDescriptor:
        def __init__(self, func):
            self.func = func
            self.options = options

        def __set_name__(self, owner, name):
            if not hasattr(owner, '__tableFieldMeta__'):
                owner.__tableFieldMeta__ = []
            # Set default name if not provided
            if getattr(self.options, 'name', None) is None:
                self.options.name = name
            # Build metadata entry: propertyKey + all options
            meta = {'propertyKey': name}
            if hasattr(self.options, '__dict__'):
                meta.update(vars(self.options))
            else:
                meta.update(self.options)
            owner.__tableFieldMeta__.append(meta)

        def __get__(self, instance, owner):
            return self.func.__get__(instance, owner)

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

    def decorator(func):
        return TableFieldDescriptor(func)

    return decorator
