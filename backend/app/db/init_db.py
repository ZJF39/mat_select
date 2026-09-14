# -*- coding: utf-8 -*-
"""数据库初始化与种子导入。

- init_db(): 执行 schema.sql（executescript）；探测 FTS5 trigram 能力，
  不支持则把 tokenize='trigram' 替换为 unicode61 重建并打印告警；最后 rebuild FTS 索引。
- seed_if_empty(): 仅当 material 为空时导入 data/categories.json / materials.json / term_alias.json；
  三份文件可能尚未生成，必须容错跳过并打印提示，不得抛异常。
  另把 DEFAULT_WEIGHTS / DEFAULT_PENALTY 写入 settings_kv（已存在不覆盖），
  app_meta 写入版本号。
- main(): 支持独立运行 `python -m app.db.init_db`
"""
import json
import sqlite3
from pathlib import Path

from app.core.config import (
    DATA_DIR,
    APP_VERSION,
    DEFAULT_WEIGHTS,
    DEFAULT_PENALTY,
)
from app.db.connection import (
    get_conn,
    now_iso,
    new_uid,
    json_dumps,
    close_conn,
)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# material 表中以 JSON 文本存储的字段（列表/字典需序列化）
JSON_COLS = {
    "aliases",
    "features",
    "cautions",
    "applications",
    "molding_process",
    "certifications",
    "limitations",
}

# 与 material 列一一对应的写入字段（不含 id 自增列）
MATERIAL_COLS = [
    "uid", "name", "short_name", "category_id", "grade_type", "aliases", "description",
    "density_min", "density_max",
    "tensile_strength_min", "tensile_strength_max",
    "elastic_modulus_min", "elastic_modulus_max",
    "elongation_min", "elongation_max",
    "notch_impact_min", "notch_impact_max",
    "hdt_min", "hdt_max",
    "service_temp_min", "service_temp_max", "service_temp_limit",
    "features", "cautions", "applications",
    "price_min", "price_max", "price_unit", "price_note",
    "molding_process", "certifications", "limitations",
    "source", "source_date", "value_type",
    "archived", "created_at", "updated_at",
]


def _trigram_supported() -> bool:
    """探测当前 SQLite 是否支持 FTS5 trigram 分词器。"""
    try:
        mem = sqlite3.connect(":memory:")
        mem.execute(
            "CREATE VIRTUAL TABLE _probe USING fts5(content, tokenize='trigram')"
        )
        mem.close()
        return True
    except Exception:
        return False


def init_db() -> None:
    conn = get_conn()
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    if not _trigram_supported():
        sql = sql.replace("tokenize='trigram'", "tokenize='unicode61'")
        print(
            "[init_db] 警告: 当前 SQLite 不支持 FTS5 trigram 分词器，"
            "已回退到 unicode61，中文子串检索能力下降。"
        )
    conn.executescript(sql)
    conn.commit()
    # 重建 FTS 索引，确保 material_fts 与 material 真实数据一致（幂等安全）
    try:
        conn.execute("INSERT INTO material_fts(material_fts) VALUES('rebuild')")
        conn.commit()
    except Exception:
        pass


def _to_json(v):
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return json_dumps(v)
    return v  # 已是字符串


def _resolve_category(conn, path, cache):
    """根据 category_path（如 ["热塑性塑料","工程塑料"]）定位 category_id。"""
    if not path:
        return None
    key = tuple(path)
    if key in cache:
        return cache[key]
    names = list(path)
    cid = None
    if len(names) >= 2:
        row = conn.execute(
            "SELECT c.id FROM category c JOIN category p ON c.parent_id=p.id "
            "WHERE p.name=? AND c.name=?",
            (names[-2], names[-1]),
        ).fetchone()
        if row:
            cid = row["id"]
    if cid is None and len(names) == 1:
        row = conn.execute(
            "SELECT id FROM category WHERE name=? AND parent_id IS NULL",
            (names[0],),
        ).fetchone()
        if row:
            cid = row["id"]
    cache[key] = cid
    return cid


def _seed_categories(conn):
    fp = DATA_DIR / "categories.json"
    if not fp.exists():
        print("[seed] 未找到 data/categories.json，跳过分类导入。")
        return
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[seed] categories.json 解析失败，已跳过：{e}")
        return
    for p_idx, parent in enumerate(data.get("categories", [])):
        pname = parent.get("name") if isinstance(parent, dict) else None
        if not pname:
            continue
        cur = conn.execute(
            "INSERT INTO category (name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
            (pname, None, p_idx, now_iso()),
        )
        pid = cur.lastrowid
        for c_idx, child in enumerate(parent.get("children", [])):
            cname = child.get("name") if isinstance(child, dict) else child
            if not cname:
                continue
            conn.execute(
                "INSERT INTO category (name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
                (cname, pid, c_idx, now_iso()),
            )


def _seed_materials(conn):
    fp = DATA_DIR / "materials.json"
    if not fp.exists():
        print("[seed] 未找到 data/materials.json，跳过材料导入。")
        return
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[seed] materials.json 解析失败，已跳过：{e}")
        return
    mats = data.get("materials", [])
    if not mats:
        print("[seed] materials.json 中无材料数据，跳过。")
        return
    cat_cache = {}
    placeholders = ", ".join(["?"] * len(MATERIAL_COLS))
    for m in mats:
        name = m.get("name")
        if not name:
            print("[seed] 跳过一条缺少 name 的材料。")
            continue
        uid = m.get("uid") or new_uid()
        cat_id = _resolve_category(conn, m.get("category_path"), cat_cache)
        row = {}
        for c in MATERIAL_COLS:
            if c == "category_id":
                row[c] = cat_id
            elif c == "uid":
                row[c] = uid
            elif c in ("created_at", "updated_at"):
                row[c] = now_iso()
            elif c == "archived":
                row[c] = m.get("archived", 0)
            elif c == "value_type":
                row[c] = m.get("value_type") or "typical"
            elif c in JSON_COLS:
                row[c] = _to_json(m.get(c))
            else:
                row[c] = m.get(c)
        conn.execute(
            f"INSERT INTO material ({', '.join(MATERIAL_COLS)}) VALUES ({placeholders})",
            [row[c] for c in MATERIAL_COLS],
        )


def _seed_term_alias(conn):
    fp = DATA_DIR / "term_alias.json"
    if not fp.exists():
        print("[seed] 未找到 data/term_alias.json，跳过术语导入。")
        return
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[seed] term_alias.json 解析失败，已跳过：{e}")
        return
    for a in data.get("aliases", []):
        conn.execute(
            "INSERT INTO term_alias (standard, synonym, type) VALUES (?,?,?)",
            (a.get("standard"), a.get("synonym"), a.get("type")),
        )


def _ensure_settings(conn):
    def put(key, value):
        exists = conn.execute(
            "SELECT key FROM settings_kv WHERE key=?", (key,)
        ).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO settings_kv (key, value, updated_at) VALUES (?,?,?)",
                (key, json_dumps(value), now_iso()),
            )

    put("weights", DEFAULT_WEIGHTS)
    put("penalty", DEFAULT_PENALTY)


def _ensure_app_meta(conn):
    exists = conn.execute(
        "SELECT key FROM app_meta WHERE key='version'"
    ).fetchone()
    if exists is None:
        conn.execute(
            "INSERT INTO app_meta (key, value) VALUES (?,?)",
            ("version", APP_VERSION),
        )


def seed_if_empty() -> None:
    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) AS c FROM material")
    empty = (cur.fetchone()["c"] or 0) == 0
    if empty:
        _seed_categories(conn)
        _seed_materials(conn)
        _seed_term_alias(conn)
    else:
        print("[seed] material 表非空，跳过种子导入。")
    _ensure_settings(conn)
    _ensure_app_meta(conn)
    conn.commit()


def main() -> None:
    init_db()
    seed_if_empty()
    print("[init_db] 初始化完成。")


if __name__ == "__main__":
    main()
