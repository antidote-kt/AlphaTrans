from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.BaseMapper import BaseMapper

class MapperMultiple:
    mapper1: BaseMapper[Employee] = None
    mapper2: BaseMapper[Employee] = None

    @staticmethod
    def getInstance1DB() -> Any:
        if MapperMultiple.mapper1 is None:
            MapperMultiple.mapper1 = BaseMapper.build({
                'class': Employee,
                'config': {
                    'name': 'RdbTest1.db',
                    'securityLevel': 'S3'
                }
            })
        return MapperMultiple.mapper1

    def getInstance2DB() -> Any:

        if MapperMultiple.mapper2 is None:
            # Build parameters: use a simple object to hold 'class' attribute
            param = type('BuildParams', (), {})()
            setattr(param, 'class', Employee)
            param.config = {
                'name': 'RdbTest2.db',
                'securityLevel': relationalStore.SecurityLevel.S3
            }
            MapperMultiple.mapper2 = BaseMapper.build(param)
        return MapperMultiple.mapper2
