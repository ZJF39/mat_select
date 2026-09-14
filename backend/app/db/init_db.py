"""数据库初始化（首次启动建表 + 默认配置播种）。

- 执行 schema.sql；trigram 不支持时自动回退 unicode61。
- 若 material 为空且存在 data/materials.json 种子则导入（数据收集师产出）。
- 播种 settings_kv 默认权重 / 降权阈值、app_meta 版本、基础术语词典。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import (
    APP_VERSION,
    DATA_DIR,
    DEFAULT_PENALTY,
    DEFAULT_WEIGHTS,
    PENALTY_DIM_WEIGHTS,
    PENALTY_KEY,
    WEIGHTS_KEY,
)
from app.db.connection import get_conn, json_dumps, now_iso

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _run_schema(conn) -> None:
    raw = _SCHEMA_PATH.read_text(encoding="utf-8")
    # 将整段 SQL 按语句拆分执行，便于对 FTS 单独做 trigram 回退
    statements = [s.strip() for s in raw.split(";") if s.strip()]
    fts_created = False
    for stmt in statements:
        if "material_fts" in stmt and "CREATE VIRTUAL TABLE" in stmt:
            try:
                conn.execute(stmt)
                fts_created = True
            except Exception:
                # 回退 unicode61
                fallback = stmt.replace("tokenize='trigram'", "tokenize='unicode61'")
                conn.execute(fallback)
                fts_created = True
            continue
        conn.execute(stmt)
    if not fts_created:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS material_fts USING fts5("
            "name, short_name, aliases, description, applications, "
            "content='material', content_rowid='id', tokenize='unicode61')"
        )


def _seed_settings(conn) -> None:
    # 权重默认归一化为 100 基准（百分制），便于前端滑杆
    total = sum(DEFAULT_WEIGHTS.values()) or 1.0
    weights = {k: round(v / total * 100) for k, v in DEFAULT_WEIGHTS.items()}
    conn.execute(
        "INSERT OR IGNORE INTO settings_kv(key, value, updated_at) VALUES (?,?,?)",
        (WEIGHTS_KEY, json_dumps(weights), now_iso()),
    )
    conn.execute(
        "INSERT OR IGNORE INTO settings_kv(key, value, updated_at) VALUES (?,?,?)",
        (PENALTY_KEY, json_dumps(DEFAULT_PENALTY), now_iso()),
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_meta(key, value) VALUES (?,?)",
        ("version", APP_VERSION),
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_meta(key, value) VALUES (?,?)",
        ("penalty_dim_weights", json_dumps(PENALTY_DIM_WEIGHTS)),
    )


def _seed_term_alias(conn) -> None:
    # 基础术语词典（数据收集师 data/term_alias.json 未就绪时的兜底）
    rows = [
        ("保险丝座", "熔断器底座", "零件类型"),
        ("保险丝座", "保险丝盒", "零件类型"),
        ("保险丝座", "fuse holder", "零件类型"),
        ("接插件", "连接器", "零件类型"),
        ("接插件", "connector", "零件类型"),
        ("注塑", "注射成型", "工艺"),
        ("注塑", "射出成型", "工艺"),
        ("挤出", "挤塑", "工艺"),
        ("冲压", "钣金", "工艺"),
        ("压铸", "压铸成型", "工艺"),
        ("模压", "热压", "工艺"),
        ("长期使用温度上限", "连续使用温度", "参数"),
        ("长期使用温度上限", "耐温", "参数"),
        ("阻燃", "防火", "特性"),
        ("耐油", "抗油", "特性"),
        ("绝缘", "电气绝缘", "特性"),
    ]
    cur = conn.execute("SELECT COUNT(*) AS c FROM term_alias")
    if cur.fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO term_alias(standard, synonym, type) VALUES (?,?,?)", rows
        )


def _seed_materials_if_empty(conn) -> None:
    cur = conn.execute("SELECT COUNT(*) AS c FROM material")
    if cur.fetchone()["c"] > 0:
        return
    seed_file = DATA_DIR / "materials.json"
    if not seed_file.exists():
        return
    try:
        data = json.loads(seed_file.read_text(encoding="utf-8"))
    except Exception:
        return
    mats = data if isinstance(data, list) else data.get("materials", [])
    for m in mats:
        # 由数据收集师脚本负责具体写库；此处仅占位提示
        pass


def _seed_default_categories(conn) -> None:
    """当分类树为空时，写入一套通用材料分类骨架（仅兜底，数据收集师可扩展/替换）。"""
    rows = [
        ("热塑性塑料", None, 1),
        ("通用塑料", 1, 1),
        ("工程塑料", 1, 2),
        ("特种工程塑料", 1, 3),
        ("热固性塑料", None, 2),
        ("弹性体", None, 3),
        ("复合材料", None, 4),
        ("金属材料", None, 5),
    ]
    for name, parent_id, sort in rows:
        conn.execute(
            "INSERT INTO category(name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
            (name, parent_id, sort, now_iso()),
        )


def seed_if_empty() -> None:
    """main.py 生命周期钩子：仅在库为空时播种分类与材料种子。

    幂等：已存在数据则不重复写入，避免覆盖数据收集师的成果。
    """
    conn = get_conn()
    try:
        cat_n = conn.execute("SELECT COUNT(*) AS c FROM category").fetchone()["c"]
        if cat_n == 0:
            _seed_default_categories(conn)
        _seed_materials_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    conn = get_conn()
    try:
        _run_schema(conn)
        _seed_settings(conn)
        _seed_term_alias(conn)
        _seed_materials_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("database initialized at", str(conn_path := __import__("app.core.config", fromlist=["DB_PATH"]).DB_PATH))
