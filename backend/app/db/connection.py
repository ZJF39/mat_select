"""SQLite 连接与通用工具（契约 §4.6(b)）。

统一提供：get_conn() / now_iso() / new_uid() / json_dumps() / json_loads()。
其他模块禁止自行取时间或拼 JSON，统一走这里，保证时区与格式一致。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.core.config import DB_PATH

_TZ = timezone(timedelta(hours=8))  # 本机时区 +08:00

# 行工厂：返回可用列名访问的 Row
Row = sqlite3.Row


def _ensure_db_file() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    """返回一个已配置（行工厂 / 外键 / 时区无关存储）的 SQLite 连接。"""
    _ensure_db_file()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    """当前时间，ISO 8601 带 +08:00 时区。"""
    return datetime.now(_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def new_uid() -> str:
    """生成全局唯一 uid（UUID4 去横杠，作为材料跨机器去重键）。"""
    return uuid.uuid4().hex


def json_dumps(obj) -> str:
    """将对象序列化为 JSON 文本（中文不转义）。"""
    return json.dumps(obj, ensure_ascii=False)


def json_loads(text):
    """解析 JSON 文本；空 / None 返回空列表（用于 JSON 列）。"""
    if text is None or text == "":
        return []
    if isinstance(text, (list, dict)):
        return text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
