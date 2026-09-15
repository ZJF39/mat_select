"""材料仓储（契约 §4.1 + PRD §4.1）。

负责 material 表的读写、JSON 列序列化、关键词检索（FTS5 + LIKE 兜底）、
变更历史（material_revision）与 diff 计算。所有 SQL 集中在此层。
"""
from __future__ import annotations

import re

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

def _expand_category_ids(ids) -> list:
    """把选中的分类 id 展开为「自身 + 全部后代分类」的 id 列表。

    必要性：材料只挂在**二级分类**上（契约 §3 / 原型 02 §0.3），点一级分类时若仍用
    `category_id IN (一级id)` 做等值匹配，命中数恒为 0 —— 表现为「点击大类显示未找到匹配材料」。
    这里按 parent_id 自顶向下 BFS 展开，使一级分类筛选等价于「其下所有子类的材料」。
    """
    rows = query_all("SELECT id, parent_id FROM category")
    children: dict = {}
    for r in rows:
        children.setdefault(r["parent_id"], []).append(r["id"])

    out: list = []
    seen = set()
    stack = [int(i) for i in ids]
    while stack:
        cur = stack.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        out.append(cur)
        stack.extend(children.get(cur, []))
    return out


# 关键词检索参与匹配的列。
#
# 列集的确定依据有两个：
#  ① PRD A3「精确检索」要求覆盖用户能看到的全部文本信息；
#  ② 客户明确的四大关注点「成本 / 加工方式 / 温度 / 使用场景」必须都可被搜到。
# 据此逐列核对后补齐了三个此前遗漏的字段：
#   molding_process —— 加工方式（客户四大关注点之一，此前搜「注塑」「冲压」「压铸」
#                      全部 0 命中，虽库中有 34 条注塑、5 条冲压、3 条压铸）；
#   cautions        —— 注意项（材料卡正面与「主要特性」并列展示，客户会搜「耐候」「尺寸」）；
#   certifications  —— 认证信息（UL94 阻燃等级、RoHS/REACH/IATF，客户选型合规必查项）。
# 注：后两者以 JSON 文本入库，LIKE 直接命中键与值，故搜「UL94」「V-0」均可召回。
SEARCH_COLS = (
    "m.name", "m.short_name", "m.aliases", "m.description",
    "m.applications", "m.features", "m.limitations", "m.grade_type",
    "c.name", "m.price_note",
    "m.molding_process", "m.cautions", "m.certifications",
)

# 查询分词分隔符：空白 + 中英文标点。
#
# 覆盖三类真实输入习惯：
#  ① 组合条件「PA66, 阻燃」「PA66/阻燃」「PA66+GF30」——用逗号/斜杠/加号分隔；
#  ② 直接粘贴的需求描述「它是一个注塑件，使用场景温度不超过 150°C。」——含句号、
#     冒号、括号等成句标点，若不切分整句会变成一个永不命中的超长 token；
#  ③ 全角括号写在材料名里（如「PA66（聚酰胺66）」），切分后两段仍各自命中同一材料。
# 注意：**不含**连字符 `-`，否则「PA66-GF30」这类牌号会被拆坏。
_SEARCH_SPLIT = re.compile(r"""[\s,，、;；/|+·。！？：（）()【】{}《》「」“”"'‘’…—～]+""")


def _like_escape(s: str) -> str:
    """转义 LIKE 通配符，避免用户输入的 % / _ 被当作模式（走 ESCAPE '\\'）。"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _squash_text(s: str) -> str:
    """去掉字符串中的全部空白（含 ASCII 空格与全角空格），用于空格不敏感匹配。"""
    return re.sub(r"[\s\u3000]+", "", s)


def _squash_sql(col: str) -> str:
    """生成「把列值里空白去掉」的 SQL 表达式，与 _squash_text 口径保持一致。

    char(12288) 是全角空格（U+3000）；中文文案里两种空格都可能出现，
    直接写全角空格字面量在源码中不可见、易被编辑器误删，故用 char() 表达。
    """
    return f"REPLACE(REPLACE({col}, ' ', ''), char(12288), '')"


def _search_tokens(q: str) -> list:
    """把查询切成若干关键词；无分隔符时整串即为一个关键词。"""
    parts = [p for p in _SEARCH_SPLIT.split(q) if p]
    return parts or [q]


def text_matches_query(text: str, q: str) -> bool:
    """判断一段文本是否命中检索词 —— **与 list_materials 的关键词口径完全一致**。

    存在的意义是「匹配规则只定义一次」：顶栏全局搜索的「场景标签」分组需要对
    applications 里的每个标签单独判定，如果那里另写一套 `q in tag` 的判断，就会出现
    「材料分组有结果、场景分组为空」的不一致（例如用户连写「抗UV」而数据写「抗 UV」、
    或用户写「保险丝 座」多词而标签是「保险丝座」）。
    """
    if not text or not q or not q.strip():
        return False
    hay = str(text).lower()
    hay_squash = _squash_text(hay)
    for tok in _search_tokens(q.strip()):
        t = tok.lower()  # 分词已按空白切开，故 token 本身不含空格
        if t not in hay and t not in hay_squash:
            return False  # 任一词不命中即整体不命中（AND 语义）
    return True


def _keyword_where(q: str, params: list) -> str:
    """按关键词生成 WHERE 片段（分词 AND、列内 OR、空格不敏感），并把参数追加到 params。"""
    groups = []
    for tok in _search_tokens(q.strip()):
        tok_squash = _squash_text(tok)
        terms = []
        for col in SEARCH_COLS:
            terms.append(f"{col} LIKE ? ESCAPE '\\'")
            params.append(f"%{_like_escape(tok)}%")
            terms.append(f"{_squash_sql(col)} LIKE ? ESCAPE '\\'")
            params.append(f"%{_like_escape(tok_squash)}%")
        groups.append("(" + " OR ".join(terms) + ")")
    return "(" + " AND ".join(groups) + ")"


def search_application_tags(q: str, limit: int = 8) -> list:
    """在 applications 中聚合命中检索词的应用场景标签（顶栏全局搜索「场景」分组）。

    与材料分组共用 text_matches_query，保证两组的召回口径一致；SQL 里只按
    「首个关键词」做一次粗筛（AND 语义下首词必命中，故粗筛是有效超集），
    避免全表 JSON 解析，同时参数走 _like_escape 转义。
    """
    q = (q or "").strip()
    if not q:
        return []
    tok = _search_tokens(q)[0]
    sql = (
        "SELECT applications FROM material WHERE archived=0 AND ("
        f"applications LIKE ? ESCAPE '\\' OR {_squash_sql('applications')} LIKE ? ESCAPE '\\')"
    )
    rows = query_all(
        sql,
        (f"%{_like_escape(tok)}%", f"%{_like_escape(_squash_text(tok))}%"),
    )
    scenes: list = []
    for r in rows:
        for tag in json_loads(r["applications"]) or []:
            if isinstance(tag, str) and tag not in scenes and text_matches_query(tag, q):
                scenes.append(tag)
        if len(scenes) >= limit:
            break
    return scenes[:limit]


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
            # 选中的可能是父分类：展开为「自身 + 全部后代」后再匹配（PRD A1/A3）
            expanded = _expand_category_ids(ids)
            ph = ",".join("?" * len(expanded))
            where.append(f"m.category_id IN ({ph})")
            params.extend(expanded)

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

    # 关键词检索：多关键词模糊匹配（模糊搜索不够强的根因修复）
    #
    # 原实现的两个硬伤：
    #  ① FTS5(trigram) 的 `MATCH '"整串"'` 是**短语**匹配，用户写「PA66 阻燃」这种多词
    #     组合时短语不存在 → 0 命中，且 FTS 一旦有命中就**替换**掉 LIKE 分支（互斥而非并集），
    #     表现为「搜不到」；
    #  ② 只索引/匹配 name、short_name、aliases、description、applications 5 列，
    #     类别名、特性、材料类型等搜不到。
    # 现改为：按分隔符切词 → 每个词在 SEARCH_COLS 内取 OR → 词与词之间取 AND。
    # 既支持任意子串模糊匹配，也支持「多个条件同时满足」的自然写法。
    #
    # 另一处召回缺口：**空格不敏感**。中文技术文案习惯在中英文/数字之间插空格
    # （实测 50 条材料中有 14 条如此，如「抗 UV 差」「长期 >80°C 易软化」「优于 PA6」），
    # 而用户输入通常连写（「抗UV」），纯 LIKE 会漏召回。故每个词再对「去掉空格的列值」
    # 匹配一次。反之（数据无空格、用户敲了空格）由分词本身就解决了——空格是分隔符。
    tokens = _search_tokens(q.strip()) if q and q.strip() else []
    if tokens:
        where.append(_keyword_where(q, params))

    # 相关性排序：首个关键词命中「名称 > 牌号 > 别名」的排前面。
    # 顶栏下拉只展示 8 条，没有相关性排序时命中顺序随机，用户会认为「搜不准」。
    rel_sql = ""
    rel_params: list = []
    if tokens:
        rel_like = f"%{_like_escape(tokens[0])}%"
        rel_sql = (
            "CASE WHEN m.name LIKE ? ESCAPE '\\' THEN 0 "
            "WHEN m.short_name LIKE ? ESCAPE '\\' THEN 1 "
            "WHEN m.aliases LIKE ? ESCAPE '\\' THEN 2 ELSE 3 END, "
        )
        rel_params = [rel_like, rel_like, rel_like]

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
        f"{base_from} WHERE {where_sql} ORDER BY {rel_sql}{sort_col} {order} "
        "LIMIT ? OFFSET ?"
    )
    params_pag = list(params) + list(rel_params) + [int(page_size), (int(page) - 1) * int(page_size)]
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
def _values_from_upsert(data: dict, only_present: bool = False) -> dict:
    """把提交体规整成「列 → 入库值」字典。

    `only_present=True` 时只输出提交体中**显式出现**的列（PUT 编辑用）：
    提交体是 `MaterialUpsert`，前端未渲染或被裁剪的字段不应被静默清空；
    显式传 `null` 仍会写入 null（用户清空意图不受影响）。
    """
    vals = {}
    for c in MATERIAL_COLS:
        if c in ("id", "uid", "created_at", "updated_at"):
            continue
        if only_present and c not in data:
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


def update_material(uid: str, data: dict, partial: bool = True) -> int:
    """更新材料并**写一份新快照**，返回新版本号（即新快照 id）。

    版本语义（PRD D3「每次变更留快照」）：一次编辑 = 一个新版本。
    v1 = 基线（若是种子/导入材料则在此刻补建）；v2/v3… = 每次编辑后的状态。
    因此 `diff(uid, new_version-1, new_version)` 即「上一版 → 本次」。

    `partial=True`（默认）按提交体出现的键合并，避免 PUT 时未提交字段被清空；
    材料包导入（overwrite 策略）同样依赖该行为，避免残缺包抹掉本地已补全的字段。
    """
    mid = get_material_id(uid)
    if mid is None:
        from app.core.errors import not_found
        raise not_found("材料不存在")
    ensure_baseline(uid)
    vals = _values_from_upsert(data, only_present=partial)
    if not vals:
        # 空提交体不产生「无变更版本」，直接返回当前最新版本号
        row = query_one(
            "SELECT id FROM material_revision WHERE material_id=? ORDER BY id DESC LIMIT 1", (mid,)
        )
        return row["id"] if row else 0
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
