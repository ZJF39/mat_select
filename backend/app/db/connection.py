"""SQLite 连接与通用工具（契约 §3 / §4.6）。

统一提供：get_conn() / close_conn() / now_iso() / new_uid() / json_dumps() / json_loads() / Row。

关键设计（不可改，全项目依赖）：
- **连接为模块级单例**（进程内复用，加锁保证线程安全）。这一点是刚需：
  `repository.base.tx()` 与模块级 `execute()/query_all()` 必须落在**同一个连接**上，
  否则 `with tx() as conn:` 块内的写入会走另一条连接、各自提交，事务原子性失效
  （导入导入流程需要「校验通过后多表原子写入」）。
- `check_same_thread=False`：FastAPI 的同步端点跑在线程池中，连接需跨线程可用，
  并发访问由 `_LOCK` 串行化。
- `PRAGMA foreign_keys=ON`（每个连接都需设置）与 `journal_mode=WAL`（落库持久）。
- 时间 / uid / JSON 统一走本模块，其他模块禁止自行取时间或拼 JSON。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import DB_PATH

_TZ = timezone(timedelta(hours=8))  # 本机时区 +08:00

# 行工厂：返回可用列名访问的 Row
Row = sqlite3.Row

_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None
_CONN_PATH: Path | None = None


def _current_db_path() -> Path:
    """当前应使用的数据库文件路径。

    `MATSELECT_DB` 优先（测试用临时库），否则回落到 config.DB_PATH。
    每次调用都重新读取，以便测试在同一进程内切换数据目录。
    """
    return Path(os.environ.get("MATSELECT_DB", str(DB_PATH)))


def get_conn() -> sqlite3.Connection:
    """返回模块级单例连接（首次调用时创建并配置 PRAGMA）。"""
    global _CONN, _CONN_PATH
    with _LOCK:
        target = _current_db_path()
        if _CONN is not None and _CONN_PATH == target:
            return _CONN
        # 数据目录被切换（测试场景）或首次调用：重建连接
        if _CONN is not None:
            try:
                _CONN.close()
            except Exception:  # noqa: BLE001 - 关闭失败不应阻断
                pass
            _CONN = None
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target), check_same_thread=False)
        conn.row_factory = Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass  # 只读介质等场景下 WAL 不可用，降级为默认日志模式
        _CONN = conn
        _CONN_PATH = target
        return conn


def close_conn() -> None:
    """关闭单例连接（应用关停 / 测试清理时调用）。"""
    global _CONN, _CONN_PATH
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            finally:
                _CONN = None
                _CONN_PATH = None


def reset_conn() -> None:
    """显式丢弃当前单例（测试切换数据目录时使用），等价于 close_conn。"""
    close_conn()


def now_iso() -> str:
    """当前时间，ISO 8601 带 +08:00 时区。全项目唯一取时间入口。"""
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
