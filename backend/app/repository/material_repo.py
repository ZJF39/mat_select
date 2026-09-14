"""材料仓储（契约 §4.1 + PRD §4.1）。

负责 material 表的读写、JSON 列序列化、关键词检索（FTS5 + LIKE 兜底）、
变更历史（material_revision）与 diff 计算。所有 SQL 集中在此层。
"""
from __future__ import annotations

from app.db.connection import json_dumps, json_loads, new_uid, now_iso
from app.repository.base import execute, query_all, query_one, scalar

ARRAY_COLS = ["aliases", "features", "applications", "molding_process", "limitations"]
OBJ_COLS = ["cautions", "certifications"]

MATERIAL_COLS = [
    "id", "uid", "name", "short_name", "category_id", "grade_type", "aliases",
    "description", "density_min", "density_max", "tensile_strength_min",
    "tensile_strength_max", "elastic_modulus_min", "elastic_modulus_max",
    "elongation_min", "elongation_max", "notch_impact_min", "notch_impact_max",
    "hdt_min", "hdt_max", "service_temp_min", "service_temp_max",
    "service_temp_limit", "features", "cautions", "applications", "price_min",
    "price_max", "price_unit", "price_note", "molding_process", "certifications",
    "limitations", "source", "source_date", "value_type", "archived",
    "created_at", "updated_at",
]


def _parse_json_cols(row: dict) -> dict:
    d = dict(row)
    for c in ARRAY_COLS:
        v = json_loads(d.get(c))
        d[c] = v if isinstance(v, list) else []
    for c in OBJ_COLS:
        v = json_loads(d.get(c))
        d[c] = v if isinstance(v, (list, dict)) else ({} if c == "certifications" else [])
    if isinstance(d.get("certifications"), list):
        d["certifications"] = {}
    return d


def _category_index() -> dict:
    rows = query_all("SELECT id, name, parent_id FROM category")
    return {r["id"]: (r["name"], r["parent_id"]) for r in rows}


def _category_path(index: dict, cat_id) -> tuple:
    name = None
    path = []
    cur = cat_id
    guard = 0
    while cur is not None and guard < 20:
        guard += 1
        node = index.get(cur)
        if not node:
            break
        name, parent = node
        path.insert(0, name)
        cur = parent
    return name, path


def _row_to_detail(row) -> dict:
    d = _parse_json_cols(dict(row))
    index = _category_index()
    cat_name, cat_path = _category_path(index, d.get("category_id"))
    card = {
        "uid": d["uid"],
        "name": d["name"],
        "short_name": d.get("short_name"),
        "category_id": d.get("category_id"),
        "category_name": cat_name,
        "category_path": cat_path,
        "grade_type": d.get("grade_type"),
        "aliases": d.get("aliases", []),
        "description": d.get("description"),
        "density_min": d.get("density_min"),
        "density_max": d.get("density_max"),
        "tensile_strength_min": d.get("tensile_strength_min"),
        "tensile_strength_max": d.get("tensile_strength_max"),
        "elastic_modulus_min": d.get("elastic_modulus_min"),
        "elastic_modulus_max": d.get("elastic_modulus_max"),
        "elongation_min": d.get("elongation_min"),
        "elongation_max": d.get("elongation_max"),
        "notch_impact_min": d.get("notch_impact_min"),
        "notch_impact_max": d.get("notch_impact_max"),
        "hdt_min": d.get("hdt_min"),
        "hdt_max": d.get("hdt_max"),
        "service_temp_min": d.get("service_temp_min"),
        "service_temp_max": d.get("service_temp_max"),
        "service_temp_limit": d.get("service_temp_limit"),
        "features": d.get("features", []),
        "cautions": d.get("cautions", []),
        "applications": d.get("applications", []),
        "price_min": d.get("price_min"),
        "price_max": d.get("price_max"),
        "price_unit": d.get("price_unit"),
        "price_note": d.get("price_note"),
        "molding_process": d.get("molding_process", []),
        "certifications": d.get("certifications", {}) or {},
        "limitations": d.get("limitations", []),
        "source": d.get("source"),
        "source_date": d.get("source_date"),
        "value_type": d.get("value_type") or "typical",
        "archived": bool(d.get("archived")),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }
    return card


def _row_to_card(row) -> dict:
    return _row_to_detail(row)


# ---------------- 检索 / 列表 ----------------
def list_materials(
    q=None, category_ids=None, processes=None, temp_min=None, price_max=None,
    flame=None, features=None, sort="updated_at", order="desc", archived=0,
    page=1, page_size=20,
):
    where = ["1=1"]
    params = []

    if archived is not None:
        where.append("m.archived = ?")
        params.append(int(archived))

    if category_ids:
        ids = [int(x) for x in str(category_ids).split(",") if x.strip().isdigit()]
        if ids:
            ph = ",".join("?" * len(ids))
            where.append(f"m.category_id IN ({ph})")
            params.extend(ids)

    if processes:
        procs = [p.strip() for p in str(processes).split(",") if p.strip()]
        for p in procs:
            where.append("m.molding_process LIKE ?")
            params.append(f"%{p}%")

    if temp_min is not None and temp_min != "":
        where.append("m.service_temp_limit >= ?")
        params.append(float(temp_min))

    if price_max is not None and price_max != "":
        where.append("(m.price_max <= ? OR (m.price_max IS NULL AND m.price_min <= ?))")
        params.extend([float(price_max), float(price_max)])

    if flame == "flame" or flame == "阻燃":
        where.append("m.features LIKE ?")
        params.append("%阻燃%")

    if features:
        feats = [f.strip() for f in str(features).split(",") if f.strip()]
        for f in feats:
            where.append("m.features LIKE ?")
            params.append(f"%{f}%")

    # 关键词：优先 FTS5 MATCH，失败/空则 LIKE 兜底
    fts_join = ""
    if q:
        q = q.strip()
        if len(q) >= 2:
            try:
                safe = q.replace('"', '""')
                rows = query_all(
                    "SELECT m.id FROM material m "
                    "JOIN material_fts f ON f.rowid = m.id "
                    "WHERE material_fts MATCH ?",
                    (f'"{safe}"',),
                )
                ids = [r["id"] for r in rows]
                if ids:
                    ph = ",".join("?" * len(ids))
                    where.append(f"m.id IN ({ph})")
                    params.extend(ids)
                else:
                    where.append(
                        "(m.name LIKE ? OR m.aliases LIKE ? OR m.description LIKE ? OR m.applications LIKE ?)"
                    )
                    like = f"%{q}%"
                    params.extend([like, like, like, like])
            except Exception:
                where.append(
                    "(m.name LIKE ? OR m.aliases LIKE ? OR m.description LIKE ? OR m.applications LIKE ?)"
                )
                like = f"%{q}%"
                params.extend([like, like, like, like])
        else:
            where.append(
                "(m.name LIKE ? OR m.aliases LIKE ? OR m.description LIKE ? OR m.applications LIKE ?)"
            )
            like = f"%{q}%"
            params.extend([like, like, like, like])

    sort_col = {
        "category_name": "c.name",
        "density": "COALESCE(m.density_max, m.density_min)",
        "service_temp_limit": "m.service_temp_limit",
        "price": "COALESCE(m.price_max, m.price_min)",
        "updated_at": "m.updated_at",
        "name": "m.name",
    }.get(sort, "m.updated_at")
    order = "DESC" if order != "asc" else "ASC"

    base_from = (
        "FROM material m LEFT JOIN category c ON m.category_id = c.id"
    )
    where_sql = " AND ".join(where)
    total = scalar(f"SELECT COUNT(*) FROM material m LEFT JOIN category c ON m.category_id=c.id WHERE {where_sql}", params)

    sql = (
        "SELECT m.*, c.name AS category_name, c.parent_id AS category_parent_id "
        f"{base_from} WHERE {where_sql} ORDER BY {sort_col} {order} "
        "LIMIT ? OFFSET ?"
    )
    params_pag = list(params) + [int(page_size), (int(page) - 1) * int(page_size)]
    rows = query_all(sql, params_pag)
    items = [_row_to_card(r) for r in rows]
    return total or 0, items


def get_material(uid: str):
    row = query_one("SELECT * FROM material WHERE uid=?", (uid,))
    if not row:
        return None
    return _row_to_detail(row)


def get_material_by_id(material_id: int):
    """按自增 id 取详情（待选清单 / 回评需要由 material_id 反查卡片）。"""
    row = query_one("SELECT * FROM material WHERE id=?", (int(material_id),))
    if not row:
        return None
    return _row_to_detail(row)


def get_material_id(uid: str):
    return scalar("SELECT id FROM material WHERE uid=?", (uid,))


# ---------------- 写入 ----------------
def _values_from_upsert(data: dict) -> dict:
    vals = {}
    for c in MATERIAL_COLS:
        if c in ("id", "uid", "created_at", "updated_at"):
            continue
        if c in ARRAY_COLS:
            vals[c] = json_dumps(data.get(c, []) or [])
        elif c in OBJ_COLS:
            vals[c] = json_dumps(data.get(c, {}) or ({} if c == "certifications" else []))
        elif c == "archived":
            # 契约 §3「空值一律 null」，但 `archived` 是过滤列（列表默认 WHERE archived=0）：
            # 若写入 NULL，因 SQL 中 `NULL = 0` 不成立，新建材料会从默认列表中「消失」。
            # DDL 的 DEFAULT 0 对显式传 NULL 不生效，故在此归一为 0/1（PRD A1/D1）。
            vals[c] = 1 if data.get(c) else 0
        elif c == "value_type":
            # ADR-05：value_type 缺省为 typical
            vals[c] = data.get(c) or "typical"
        else:
            vals[c] = data.get(c)
    return vals


def create_material(data: dict) -> str:
    uid = new_uid()
    vals = _values_from_upsert(data)
    cols = ["uid"] + list(vals.keys()) + ["created_at", "updated_at"]
    placeholders = ",".join("?" * len(cols))
    params = [uid] + [vals[c] for c in vals.keys()] + [now_iso(), now_iso()]
    sql = f"INSERT INTO material({','.join(cols)}) VALUES({placeholders})"
    execute(sql, params)
    # 初始快照
    _snapshot(uid, "创建")
    return uid


def ensure_baseline(uid: str):
    """确保材料存在 v1 基线快照，返回基线版本 id。

    必要性：种子导入（`init_db._seed_materials`）与材料包导入（`io_service`）
    走的是裸 INSERT，不经过 `create_material`，因此这些材料**没有历史快照**；
    若不补基线，首次编辑后 `new_version=1` 且「上一版」不存在，
    会导致 PRD D3 的变更历史 / diff / 恢复功能对全部种子材料失效。
    """
    mid = get_material_id(uid)
    if mid is None:
        return None
    row = query_one(
        "SELECT id FROM material_revision WHERE material_id=? ORDER BY id LIMIT 1", (mid,)
    )
    if row:
        return row["id"]
    return _snapshot(uid, "基线", snapshot=get_material(uid))


def update_material(uid: str, data: dict) -> int:
    """更新材料并**写一份新快照**，返回新版本号（即新快照 id）。

    版本语义（PRD D3「每次变更留快照」）：一次编辑 = 一个新版本。
    v1 = 基线（若是种子/导入材料则在此刻补建）；v2/v3… = 每次编辑后的状态。
    因此 `diff(uid, new_version-1, new_version)` 即「上一版 → 本次」。
    """
    mid = get_material_id(uid)
    if mid is None:
        from app.core.errors import not_found
        raise not_found("材料不存在")
    ensure_baseline(uid)
    vals = _values_from_upsert(data)
    set_clause = ", ".join(f"{c}=?" for c in vals.keys()) + ", updated_at=?"
    params = [vals[c] for c in vals.keys()] + [now_iso()]
    execute(f"UPDATE material SET {set_clause} WHERE uid=?", params + [uid])
    new = get_material(uid)
    return _snapshot(uid, "编辑", snapshot=new)


def _snapshot(uid: str, note: str, snapshot: dict = None) -> int:
    mid = get_material_id(uid)
    if snapshot is None:
        snapshot = get_material(uid)
    payload = json_dumps(snapshot, ensure_ascii=False) if False else json_dumps(snapshot)
    rid = execute(
        "INSERT INTO material_revision(material_id, snapshot, changed_at, change_note) VALUES (?,?,?,?)",
        (mid, payload, now_iso(), note),
    )
    return rid


def list_revisions(uid: str):
    mid = get_material_id(uid)
    if mid is None:
        return []
    rows = query_all(
        "SELECT id AS version, changed_at, change_note FROM material_revision "
        "WHERE material_id=? ORDER BY id",
        (mid,),
    )
    return [dict(r) for r in rows]


def get_revision_snapshot(mid: int, version: int) -> dict:
    row = query_one(
        "SELECT snapshot FROM material_revision WHERE material_id=? AND id=?",
        (mid, version),
    )
    if not row:
        return None
    return json_loads(row["snapshot"])


def restore_revision(uid: str, version: int) -> int:
    mid = get_material_id(uid)
    if mid is None:
        from app.core.errors import not_found
        raise not_found("材料不存在")
    snap = get_revision_snapshot(mid, version)
    if snap is None:
        from app.core.errors import not_found
        raise not_found("版本不存在")
    ensure_baseline(uid)
    # 用历史快照覆盖当前内容
    data = {}
    for c in MATERIAL_COLS:
        if c in ("id", "uid", "created_at", "updated_at", "category_name", "category_path",
                 "negative_feedback", "recent_revisions"):
            continue
        if c in snap:
            data[c] = snap[c]
    vals = _values_from_upsert(data)
    set_clause = ", ".join(f"{c}=?" for c in vals.keys()) + ", updated_at=?"
    params = [vals[c] for c in vals.keys()] + [now_iso()]
    execute(f"UPDATE material SET {set_clause} WHERE uid=?", params + [uid])
    new = get_material(uid)
    # 恢复产出一个新版本（不删历史），符合「恢复即一次变更」
    return _snapshot(uid, f"恢复至v{version}", snapshot=new)


# ---------------- 反馈聚合 ----------------
def material_feedback(uid: str):
    mid = get_material_id(uid)
    if mid is None:
        return []
    rows = query_all(
        "SELECT dimension, COUNT(*) AS count, MAX(active) AS active "
        "FROM material_negative_feedback WHERE material_id=? GROUP BY dimension",
        (mid,),
    )
    return [{"dimension": r["dimension"], "count": r["count"], "active": bool(r["active"])} for r in rows]


def recent_revisions(uid: str, limit: int = 3):
    mid = get_material_id(uid)
    if mid is None:
        return []
    rows = query_all(
        "SELECT changed_at, change_note FROM material_revision WHERE material_id=? "
        "ORDER BY id DESC LIMIT ?",
        (mid, limit),
    )
    return [{"changed_at": r["changed_at"], "summary": r["change_note"]} for r in rows]


# ---------------- diff ----------------
DIFF_SPECS = [
    ("name", "名称", "scalar"),
    ("short_name", "简称", "scalar"),
    ("category_name", "分类", "scalar"),
    ("grade_type", "材料类型", "scalar"),
    ("description", "概述", "scalar"),
    ("aliases", "别名", "array"),
    ("density", "密度 (g/cm³)", "range"),
    ("tensile_strength", "拉伸强度 (MPa)", "range"),
    ("elastic_modulus", "弹性模量 (GPa)", "range"),
    ("elongation", "断裂伸长率 (%)", "range"),
    ("notch_impact", "缺口冲击 (kJ/m²)", "range"),
    ("hdt", "热变形温度 (°C)", "range"),
    ("service_temp", "长期使用温度 (°C)", "range2"),
    ("service_temp_limit", "长期耐温上限 (°C)", "scalar"),
    ("features", "主要特性", "array"),
    ("cautions", "注意项", "array_obj"),
    ("applications", "典型应用", "array"),
    ("price", "参考价", "price"),
    ("price_note", "价格备注", "scalar"),
    ("molding_process", "成型工艺", "array"),
    ("certifications", "认证合规", "object"),
    ("limitations", "失效模式", "array"),
    ("source", "数据来源", "scalar"),
    ("source_date", "来源日期", "scalar"),
    ("value_type", "数值类型", "scalar"),
]


def _fmt_range(lo, hi):
    if lo is None and hi is None:
        return None
    if lo is None:
        return f"≤{hi}" if hi is not None else None
    if hi is None:
        return f"{lo}"
    return f"{lo}–{hi}"


def _spec_raw(snap: dict, key: str, kind: str):
    if kind == "range":
        return _fmt_range(snap.get(f"{key}_min"), snap.get(f"{key}_max"))
    if kind == "range2":
        return _fmt_range(snap.get("service_temp_min"), snap.get("service_temp_max"))
    if kind == "price":
        lo, hi, unit = snap.get("price_min"), snap.get("price_max"), snap.get("price_unit")
        if lo is None and hi is None:
            return None
        s = _fmt_range(lo, hi)
        return f"{s} {unit}" if unit else s
    if kind == "array":
        v = snap.get(key)
        return [str(x) for x in v] if isinstance(v, list) else []
    if kind == "array_obj":
        v = snap.get(key)
        out = []
        if isinstance(v, list):
            for it in v:
                if isinstance(it, dict):
                    out.append(f"{it.get('type','')}: {it.get('content','')}".strip(": ").strip())
        return out
    if kind == "object":
        v = snap.get(key) or {}
        if not isinstance(v, dict):
            return []
        out = []
        for k, val in v.items():
            if val is None or val == "" or val is False:
                continue
            out.append(f"{k}: {val}")
        return out
    # scalar
    v = snap.get(key)
    if v is None or v == "":
        return None
    return str(v)


def compute_diff(uid: str, a: int, b: int = None) -> dict:
    """计算两个版本之间的字段级 diff，返回 DiffPayload 字典。"""
    mid = get_material_id(uid)
    if mid is None:
        from app.core.errors import not_found
        raise not_found("材料不存在")
    snap_a = get_revision_snapshot(mid, a)
    if snap_a is None:
        from app.core.errors import not_found
        raise not_found("源版本不存在")
    if b is None:
        snap_b = get_material(uid) or {}
    else:
        snap_b = get_revision_snapshot(mid, b)
        if snap_b is None:
            from app.core.errors import not_found
            raise not_found("目标版本不存在")

    rows = []
    for key, cn, kind in DIFF_SPECS:
        before = _spec_raw(snap_a, key, kind)
        after = _spec_raw(snap_b, key, kind)
        b_empty = before is None or (isinstance(before, list) and len(before) == 0)
        a_empty = after is None or (isinstance(after, list) and len(after) == 0)
        if b_empty and a_empty:
            continue
        if b_empty and not a_empty:
            t = "add"
        elif not b_empty and a_empty:
            t = "remove"
        elif before != after:
            t = "modify"
        else:
            continue
        row = {
            "field": cn,
            "key": key,
            "type": t,
            "before": None if isinstance(before, list) else before,
            "after": None if isinstance(after, list) else after,
            "before_items": before if isinstance(before, list) else [],
            "after_items": after if isinstance(after, list) else [],
        }
        rows.append(row)

    summary = f"本次修改了 {len(rows)} 个字段"
    return {"from_version": a, "to_version": b if b is not None else -1, "summary": summary, "rows": rows}
