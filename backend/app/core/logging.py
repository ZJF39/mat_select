"""操作日志（契约 §3.1 + PRD §6 审计）。

统一写入 operation_log 表，禁止其他模块直接写日志表。
"""
from __future__ import annotations

from app.db.connection import get_conn, now_iso
from app.repository.base import BaseRepository


def write_log(action: str, target: str = "", detail=None) -> None:
    """写入一条操作日志。

    action: 新增材料 / 编辑材料 / 归档 / 导入 / 导出 / 回评 ...
    target: 对象描述（材料名 / 任务名 / 文件名）
    detail: 可选的结构化信息（会被 json 序列化）

    ⚠️ 铁律：**不得关闭连接**。`app.db.connection.get_conn()` 返回模块级单例，
    一旦在此 close，同进程后续任何查询都会抛
    `sqlite3.ProgrammingError: Cannot operate on a closed database`。
    连接的生命周期由 `main.py` lifespan 调用 `connection.close_conn()` 统一管理。
    """
    import json

    detail_str = None
    if detail is not None:
        detail_str = json.dumps(detail, ensure_ascii=False)
    conn = get_conn()
    conn.execute(
        "INSERT INTO operation_log(at, action, target, detail) VALUES (?,?,?,?)",
        (now_iso(), action, target or "", detail_str),
    )
    conn.commit()
