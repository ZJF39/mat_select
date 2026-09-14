# -*- coding: utf-8 -*-
"""Repository 基础层：连接 / 事务 / Row 工具（签名冻结，后端专家依赖）。

设计要点（契约 §2 / §4.6）：
- 所有 SQL 集中在 repository 层，业务代码不直接碰 sqlite3；
- 本文件是 SQLite↔PostgreSQL 可迁移的「口子」：若二期换库，
  只需替换 connection 与 repository 实现，业务逻辑零改动。
- 时间 / uid 统一走 connection.now_iso() / new_uid()，禁止在别处取时间。

对外暴露（均不可改签名）：
- query_all(sql, params=()) -> list[Row]
- query_one(sql, params=()) -> Row | None
- scalar(sql, params=()) -> Any
- execute(sql, params=()) -> int（lastrowid）
- execute_many(sql, seq)
- rowcount(sql, params=()) -> int
- tx() 上下文管理器（异常回滚）
- 静态方法 BaseRepository.now_iso() / new_uid()
"""
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, List

from app.db.connection import (
    get_conn,
    now_iso as _now_iso,
    new_uid as _new_uid,
)

# 对外暴露 Row 类型，便于后端专家做类型标注
Row = sqlite3.Row


def query_all(sql: str, params: Iterable = ()) -> List[Row]:
    conn = get_conn()
    return conn.execute(sql, tuple(params)).fetchall()


def query_one(sql: str, params: Iterable = ()) -> "Row | None":
    conn = get_conn()
    return conn.execute(sql, tuple(params)).fetchone()


def scalar(sql: str, params: Iterable = ()) -> Any:
    conn = get_conn()
    row = conn.execute(sql, tuple(params)).fetchone()
    if row is None:
        return None
    return row[0]


def execute(sql: str, params: Iterable = ()) -> int:
    conn = get_conn()
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur.lastrowid


def execute_many(sql: str, seq: Iterable) -> int:
    conn = get_conn()
    cur = conn.executemany(sql, seq)
    conn.commit()
    return cur.rowcount


def rowcount(sql: str, params: Iterable = ()) -> int:
    conn = get_conn()
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur.rowcount


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """事务上下文：正常提交，异常回滚并向上抛出。"""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


class BaseRepository:
    """后端 repository 可继承；提供的静态方法即上述模块函数，便于 classmethod 风格调用。"""

    @staticmethod
    def now_iso() -> str:
        return _now_iso()

    @staticmethod
    def new_uid() -> str:
        return _new_uid()

    @staticmethod
    def query_all(sql: str, params: Iterable = ()) -> List[Row]:
        return query_all(sql, params)

    @staticmethod
    def query_one(sql: str, params: Iterable = ()) -> "Row | None":
        return query_one(sql, params)

    @staticmethod
    def scalar(sql: str, params: Iterable = ()) -> Any:
        return scalar(sql, params)

    @staticmethod
    def execute(sql: str, params: Iterable = ()) -> int:
        return execute(sql, params)

    @staticmethod
    def execute_many(sql: str, seq: Iterable) -> int:
        return execute_many(sql, seq)

    @staticmethod
    def rowcount(sql: str, params: Iterable = ()) -> int:
        return rowcount(sql, params)

    @staticmethod
    def tx():
        """转发到模块级 tx()，使 self.tx() / BaseRepository.tx() 与直接 import 三种用法一致。"""
        return tx()
