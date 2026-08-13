from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import *
from rdbplus.src.main.ets.log.Logger import Logger

class DbLogger(Logger):
    def debug(self, *args: str) -> None:
            import logging
            logging.debug('rdb ' + ' '.join(args))

    def info(self, *args: str) -> None:
            print('rdb ' + ' '.join(args))

    def warn(self, *args: str) -> None:
            import sys
            print('rdb ' + ' '.join(args), file=sys.stderr)

    def error(self, *args: str) -> None:
            import sys
            print('rdb ' + ' '.join(args), file=sys.stderr)
