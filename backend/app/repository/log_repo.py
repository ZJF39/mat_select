# -*- coding: utf-8 -*-
"""操作日志仓储（契约 §4.6(b) `operation_log` / §4.4 `GET /api/logs`）。

⚠️ 已知底座缺陷（本仓储绕开的原因，勿回退）：
`app/core/logging.py::write_log()` 在写完后执行 `conn.close()`，而
`app/db/connection.get_conn()` 的模块级单例 `_CONN` 仍指向该已关闭连接，
于是**同进程后续任何查询**都会抛
`sqlite3.ProgrammingError: Cannot operate on a closed database`（已实测复现）。
由于 `core/**` 属架构师所有、后端专家不得修改，这里在 **repository 层**
直接落库（SQL 集中在仓储层，符合契约 §2 的分层约定），表名与列名与
`write_log` 完全一致，保证 `GET /api/logs` 与审计语义不变。
已将该缺陷写入交付回报，交技术负责人修复底座。
"""
from __future__ import annotations

from app.db.connection import json_dumps, now_iso
from app.repository.base import execute, query_all


def log(action: str, target: str = "", detail=None) -> int:
    """写入一条操作日志，返回日志 id。"""
    detail_str = json_dumps(detail) if detail is not None else None
    return execute(
        "INSERT INTO operation_log(at, action, target, detail) VALUES (?,?,?,?)",
        (now_iso(), action, target or "", detail_str),
    )


def list_logs(limit: int = 50):
    """按时间倒序返回最近 limit 条日志。"""
    rows = query_all(
        "SELECT id, at, action, target FROM operation_log ORDER BY id DESC LIMIT ?",
        (int(limit),),
    )
    return [dict(r) for r in rows]
