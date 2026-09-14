"""数据库初始化（首次启动建表 + 种子导入 + 默认配置播种）。

职责边界：
- 建表：执行 `schema.sql`（trigram 不可用时自动回退 unicode61）。
- 播种：`init_db()` 幂等写入默认权重 / 降权阈值 / 版本号 / 兜底术语词典。
- 种子导入：`seed_if_empty()` 在库为空时导入数据收集师产出的
  `data/categories.json` / `data/materials.json` / `data/term_alias.json`。

⚠️ 两条铁律（踩过坑，勿改）：
1. 本模块**不得关闭连接**。`app.db.connection.get_conn()` 是模块级单例，
   一旦 close，全局后续调用会报 `Cannot operate on a closed database`。
   应用关停时的关闭交给 `main.py` lifespan 调用 `connection.close_conn()`。
2. 建表**必须**用 `executescript` 整体执行，不能按 ";" 拆分后逐条 execute：
   FTS5 同步触发器体是 `BEGIN ... END;`，内部含分号，拆分会产生
   `sqlite3.OperationalError: incomplete input`。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import (
    APP_VERSION,
    DATA_DIR,
    DEFAULT_PENALTY,
    DEFAULT_WEIGHTS,
    PENALTY_DIM_WEIGHTS,
    PENALTY_KEY,
    SEED_DIR,
    WEIGHTS_KEY,
)
from app.db.connection import get_conn, json_dumps, new_uid, now_iso

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# material 表中以 JSON 文本存储的列（写入前需序列化）
_JSON_COLS = {
    "aliases",
    "features",
    "cautions",
    "applications",
    "molding_process",
    "certifications",
    "limitations",
}
# 空值语义：对象型列给 {}，其余数组型列给 []
_JSON_OBJ_COLS = {"certifications"}


# --------------------------------------------------------------------------- #
# 建表
# --------------------------------------------------------------------------- #
def _supports_trigram(conn) -> bool:
    """探测当前 SQLite 是否支持 FTS5 trigram 分词器（trigram 需 SQLite >= 3.34）。"""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(x, tokenize='trigram')"
        )
        conn.execute("DROP TABLE IF EXISTS _fts_probe")
        return True
    except Exception:  # noqa: BLE001 - 不支持时回退 unicode61
        try:
            conn.execute("DROP TABLE IF EXISTS _fts_probe")
        except Exception:  # noqa: BLE001
            pass
        return False


def _run_schema(conn) -> None:
    """整体执行 schema.sql（见模块 docstring 铁律 2）。"""
    raw = _SCHEMA_PATH.read_text(encoding="utf-8")
    if not _supports_trigram(conn):
        raw = raw.replace("tokenize='trigram'", "tokenize='unicode61'")
    conn.executescript(raw)
    conn.commit()


# --------------------------------------------------------------------------- #
# 默认配置播种
# --------------------------------------------------------------------------- #
def _seed_settings(conn) -> None:
    """写入默认权重（百分制）与降权阈值，已存在则不覆盖。"""
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


# 兜底术语词典（`data/term_alias.json` 缺失时使用）
_FALLBACK_ALIASES: list[tuple[str, str, str]] = [
    ("保险丝座", "熔断器底座", "零件类型"),
    ("保险丝座", "保险丝盒", "零件类型"),
    ("保险丝座", "fuse holder", "零件类型"),
    ("连接器", "接插件", "零件类型"),
    ("连接器", "connector", "零件类型"),
    ("ECU壳体", "控制器外壳", "零件类型"),
    ("传感器支架", "传感器座", "零件类型"),
    ("继电器底座", "继电器座", "零件类型"),
    ("卡扣", "卡子", "零件类型"),
    ("注塑", "注射成型", "工艺"),
    ("注塑", "射出成型", "工艺"),
    ("挤出", "挤塑", "工艺"),
    ("压铸", "压力铸造", "工艺"),
    ("长期使用温度上限", "连续使用温度", "参数"),
    ("长期使用温度上限", "耐温", "参数"),
    ("拉伸强度", "抗拉强度", "参数"),
    ("缺口冲击强度", "悬臂梁冲击强度", "参数"),
    ("阻燃等级", "UL94", "参数"),
]

# 兜底分类骨架（`data/categories.json` 缺失时使用）
_FALLBACK_CATEGORIES: list[tuple[str, list[str]]] = [
    ("热塑性塑料", ["通用塑料", "工程塑料", "特种工程塑料"]),
    ("热固性塑料", ["酚醛树脂", "环氧树脂", "不饱和聚酯"]),
    ("金属", ["钢材", "铝合金", "铜合金", "锌合金", "镁合金"]),
    ("弹性体", ["热塑性弹性体", "橡胶"]),
    ("复合材料", ["玻璃纤维增强", "碳纤维增强"]),
]


# --------------------------------------------------------------------------- #
# 种子文件读取
# --------------------------------------------------------------------------- #
def _load_json(filename: str) -> Any | None:
    """读取 JSON 种子文件；缺失或损坏返回 None（不抛异常）。

    查找顺序（打包运行时二者不同）：
      1) 可写数据目录 `DATA_DIR`   —— 允许用户修改/替换种子
      2) 只读种子目录 `SEED_DIR`   —— 打包时随 exe 分发的出厂种子
    非打包运行时两者都指向 `<项目根>/data`，行为与打包前一致。
    """
    for base in (DATA_DIR, SEED_DIR):
        path = base / filename
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[seed] 解析 {path} 失败，跳过：{exc}")
            return None
    print(f"[seed] 未找到 {filename}（已查 {DATA_DIR} 与 {SEED_DIR}），跳过")
    return None


# --------------------------------------------------------------------------- #
# 分类导入
# --------------------------------------------------------------------------- #
def _seed_categories(conn) -> int:
    """导入两级分类树；返回插入条数。文件缺失时写兜底骨架。"""
    data = _load_json("categories.json")
    nodes: list[tuple[str, list[str]]] = []

    if isinstance(data, dict) and isinstance(data.get("categories"), list):
        for item in data["categories"]:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            children = [
                c.get("name")
                for c in (item.get("children") or [])
                if isinstance(c, dict) and c.get("name")
            ]
            nodes.append((str(item["name"]), children))
    elif isinstance(data, list):
        # 兼容扁平结构 [{name, parent_name}]
        parents = [d for d in data if isinstance(d, dict) and d.get("name")]
        nodes = [(str(d["name"]), []) for d in parents]

    if not nodes:
        nodes = _FALLBACK_CATEGORIES
        print("[seed] 使用兜底分类骨架（未读到有效 categories.json）")

    inserted = 0
    sort = 0
    for name, children in nodes:
        sort += 1
        cur = conn.execute(
            "INSERT INTO category(name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
            (name, None, sort, now_iso()),
        )
        inserted += 1
        parent_id = cur.lastrowid
        for i, child in enumerate(children, start=1):
            conn.execute(
                "INSERT INTO category(name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
                (child, parent_id, i, now_iso()),
            )
            inserted += 1
    return inserted


def _category_map(conn) -> dict[str, int]:
    """分类名 → id（子类优先，因为材料用 category_path 末位定位）。"""
    mapping: dict[str, int] = {}
    for row in conn.execute("SELECT id, name FROM category ORDER BY id"):
        mapping[row["name"]] = row["id"]
    return mapping


# --------------------------------------------------------------------------- #
# 材料导入
# --------------------------------------------------------------------------- #
def _seed_materials(conn) -> int:
    """导入 data/materials.json；返回插入条数。

    采用「按 material 表实际列名映射」的通用写法（PRAGMA table_info），
    避免字段增删后此处与实际表结构脱节。
    """
    data = _load_json("materials.json")
    if data is None:
        return 0
    mats = data if isinstance(data, list) else data.get("materials", [])
    if not isinstance(mats, list):
        return 0

    cols = [r["name"] for r in conn.execute("PRAGMA table_info(material)")]
    cat_map = _category_map(conn)
    now = now_iso()
    inserted = 0

    for m in mats:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "").strip()
        if not name:
            continue

        row: dict[str, Any] = {}
        for key, value in m.items():
            if key == "category_path" or key not in cols:
                continue
            if key in _JSON_COLS:
                if value is None:
                    value = {} if key in _JSON_OBJ_COLS else []
                row[key] = json_dumps(value)
            else:
                row[key] = value

        # uid / 分类 / 审计字段 兜底
        row.setdefault("uid", new_uid())
        row["name"] = name
        if "category_id" not in row or row.get("category_id") is None:
            path = m.get("category_path") or []
            if isinstance(path, list) and path:
                row["category_id"] = cat_map.get(str(path[-1]))
        row.setdefault("value_type", "typical")
        row.setdefault("archived", 0)
        row.setdefault("created_at", now)
        row.setdefault("updated_at", now)

        keys = [k for k in row if k in cols]
        placeholders = ",".join("?" for _ in keys)
        sql = f"INSERT INTO material ({','.join(keys)}) VALUES ({placeholders})"
        try:
            conn.execute(sql, tuple(row[k] for k in keys))
            inserted += 1
        except Exception as exc:  # noqa: BLE001 - 单条失败不阻断其余材料
            print(f"[seed] 材料「{name}」写入失败，已跳过：{exc}")
    return inserted


# --------------------------------------------------------------------------- #
# 术语词典导入
# --------------------------------------------------------------------------- #
def _seed_term_aliases(conn) -> int:
    """导入 data/term_alias.json；返回插入条数。文件缺失时写兜底词典。"""
    data = _load_json("term_alias.json")
    triples: list[tuple[str, str, str]] = []

    if isinstance(data, dict) and isinstance(data.get("aliases"), list):
        for a in data["aliases"]:
            if not isinstance(a, dict):
                continue
            std, syn = a.get("standard"), a.get("synonym")
            if std and syn:
                triples.append((str(std), str(syn), str(a.get("type") or "")))
    elif isinstance(data, list):
        for a in data:
            if isinstance(a, dict) and a.get("standard") and a.get("synonym"):
                triples.append(
                    (str(a["standard"]), str(a["synonym"]), str(a.get("type") or ""))
                )

    if not triples:
        triples = _FALLBACK_ALIASES
        print("[seed] 使用兜底术语词典（未读到有效 term_alias.json）")

    for std, syn, typ in triples:
        conn.execute(
            "INSERT INTO term_alias(standard, synonym, type) VALUES (?,?,?)",
            (std, syn, typ),
        )
    return len(triples)


# --------------------------------------------------------------------------- #
# 对外入口
# --------------------------------------------------------------------------- #
def init_db() -> None:
    """建表 + 播种默认配置（幂等；不关闭单例连接）。"""
    conn = get_conn()
    _run_schema(conn)
    _seed_settings(conn)
    conn.commit()


def seed_if_empty() -> None:
    """库为空时导入种子数据（幂等；不关闭单例连接）。"""
    conn = get_conn()

    material_n = conn.execute("SELECT COUNT(*) AS c FROM material").fetchone()["c"]
    if material_n == 0:
        cat_n = conn.execute("SELECT COUNT(*) AS c FROM category").fetchone()["c"]
        if cat_n == 0:
            inserted_cat = _seed_categories(conn)
            print(f"[seed] 已导入分类 {inserted_cat} 条")
        inserted_mat = _seed_materials(conn)
        if inserted_mat:
            print(f"[seed] 已导入材料 {inserted_mat} 条")

    alias_n = conn.execute("SELECT COUNT(*) AS c FROM term_alias").fetchone()["c"]
    if alias_n == 0:
        inserted_alias = _seed_term_aliases(conn)
        print(f"[seed] 已导入术语 {inserted_alias} 条")

    conn.commit()


def main() -> None:
    """独立运行入口：`python -m app.db.init_db`。"""
    init_db()
    seed_if_empty()
    conn = get_conn()
    counts = {
        t: conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        for t in ("category", "material", "term_alias")
    }
    print(
        "[init_db] 初始化完成。"
        f" 分类={counts['category']} 材料={counts['material']} 术语={counts['term_alias']}"
    )


if __name__ == "__main__":
    main()
