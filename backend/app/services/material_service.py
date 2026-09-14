# -*- coding: utf-8 -*-
"""材料 / 分类 / 检索 业务服务（契约 §4.1–§4.2、PRD A1–A3、D1–D4）。

职责：
- 材料 CRUD、变更留痕（material_revision）、Git 式 diff、版本恢复
- 精确检索（按牌号/别名/类别/参数区间/场景标签）+ 全局搜索
- 分类体系维护

说明：SQL 全部在 repository 层；本层只做规则与编排。
"""
from __future__ import annotations

from app.core.errors import not_found, validation_error
from app.core.logging import write_log
from app.db.connection import json_loads
from app.repository import category_repo, material_repo, task_repo
from app.repository.base import query_all

# ---------------------------------------------------------------- 材料：读

CARD_FIELDS = (
    "uid", "name", "short_name", "category_id", "category_name", "category_path",
    "grade_type", "aliases", "density_min", "density_max", "service_temp_limit",
    "price_min", "price_max", "price_unit", "features", "molding_process", "archived",
)


def to_card(detail: dict) -> dict:
    """MaterialDetail → MaterialCard（列表/推荐卡片只暴露卡片字段）。"""
    return {k: detail.get(k) for k in CARD_FIELDS}


def list_materials(
    q=None, category_ids=None, processes=None, temp_min=None, price_max=None,
    flame=None, features=None, sort="updated_at", order="desc", archived=0,
    page=1, page_size=20,
):
    """列表/检索：返回 (total, items[卡片])。条件之间为 AND 交集（PRD A1/A3）。"""
    try:
        page = max(1, int(page or 1))
        page_size = min(500, max(1, int(page_size or 20)))
    except (TypeError, ValueError):
        raise validation_error("分页参数非法")
    total, items = material_repo.list_materials(
        q=q, category_ids=category_ids, processes=processes, temp_min=temp_min,
        price_max=price_max, flame=flame, features=features, sort=sort, order=order,
        archived=archived, page=page, page_size=page_size,
    )
    return total, [to_card(i) for i in items]


def get_detail(uid: str) -> dict:
    """材料详情：含历史负面反馈聚合与最近 3 条变更（原型 02 §03）。"""
    detail = material_repo.get_material(uid)
    if detail is None:
        raise not_found("材料不存在")
    detail["negative_feedback"] = material_repo.material_feedback(uid)
    detail["recent_revisions"] = material_repo.recent_revisions(uid, limit=3)
    return detail


# ---------------------------------------------------------------- 材料：写


def create_material(payload: dict) -> dict:
    data = dict(payload)
    if not (data.get("name") or "").strip():
        raise validation_error("材料名称不能为空")
    _validate_ranges(data)
    uid = material_repo.create_material(data)
    write_log("新增材料", data.get("name") or "", {"uid": uid})
    return get_detail(uid)


def update_material(uid: str, payload: dict) -> tuple[dict, int]:
    """更新材料（直接生效，无审核）。返回 (详情, 新版本号)。"""
    if material_repo.get_material(uid) is None:
        raise not_found("材料不存在")
    data = dict(payload)
    if not (data.get("name") or "").strip():
        raise validation_error("材料名称不能为空")
    _validate_ranges(data)
    new_version = material_repo.update_material(uid, data)
    write_log("编辑材料", data.get("name") or "", {"uid": uid, "version": new_version})
    return get_detail(uid), new_version


def archive_material(uid: str) -> dict:
    """归档（PRD Q7：只归档不删除）。"""
    detail = material_repo.get_material(uid)
    if detail is None:
        raise not_found("材料不存在")
    from app.repository.base import execute  # 局部导入避免污染模块顶层

    execute("UPDATE material SET archived=1, updated_at=? WHERE uid=?", (_now(), uid))
    write_log("归档材料", detail["name"], {"uid": uid})
    return get_detail(uid)


def _now() -> str:
    from app.db.connection import now_iso

    return now_iso()


# 区间字段：min ≤ max 校验（原型 02 §07）
_RANGE_KEYS = (
    "density", "tensile_strength", "elastic_modulus", "elongation",
    "notch_impact", "hdt", "price",
)


def _validate_ranges(data: dict) -> None:
    for k in _RANGE_KEYS:
        lo, hi = data.get(f"{k}_min"), data.get(f"{k}_max")
        if lo is not None and hi is not None and float(lo) > float(hi):
            raise validation_error(f"{k} 的下限不能大于上限")
    lo, hi = data.get("service_temp_min"), data.get("service_temp_max")
    if lo is not None and hi is not None and float(lo) > float(hi):
        raise validation_error("长期使用温度范围的下限不能大于上限")


# ---------------------------------------------------------------- 变更历史


def list_revisions(uid: str) -> list[dict]:
    if material_repo.get_material_id(uid) is None:
        raise not_found("材料不存在")
    return material_repo.list_revisions(uid)


def diff(uid: str, a: int, b: int | None = None) -> dict:
    return material_repo.compute_diff(uid, int(a), None if b is None else int(b))


def restore(uid: str, version: int) -> tuple[dict, int]:
    new_version = material_repo.restore_revision(uid, int(version))
    write_log("恢复版本", uid, {"to_version": version, "new_version": new_version})
    return get_detail(uid), new_version


# ---------------------------------------------------------------- 材料反馈


def material_feedback(uid: str) -> list[dict]:
    if material_repo.get_material_id(uid) is None:
        raise not_found("材料不存在")
    return material_repo.material_feedback(uid)


def clear_material_feedback(uid: str) -> dict:
    mid = material_repo.get_material_id(uid)
    if mid is None:
        raise not_found("材料不存在")
    from app.repository.feedback_repo import delete_negative_by_material

    delete_negative_by_material(mid)
    write_log("清空材料反馈", uid)
    return {"ok": True}


# ---------------------------------------------------------------- 分类


def category_tree() -> list[dict]:
    return category_repo.list_tree()


def create_category(name: str, parent_id=None) -> dict:
    cid = category_repo.create(name, parent_id)
    write_log("新增分类", name)
    return _category_node(cid)


def patch_category(cid: int, name: str) -> dict:
    category_repo.patch(int(cid), name)
    write_log("重命名分类", name)
    return _category_node(int(cid))


def delete_category(cid: int) -> dict:
    category_repo.delete(int(cid))
    write_log("删除分类", str(cid))
    return {"ok": True}


def _category_node(cid: int) -> dict:
    row = query_all(
        "SELECT id, name, parent_id, sort_order, created_at FROM category WHERE id=?", (cid,)
    )
    if not row:
        raise not_found("分类不存在")
    node = dict(row[0])
    node["count"] = 0
    node["children"] = []
    return node


# ---------------------------------------------------------------- 全局搜索


def global_search(q: str, limit: int = 8) -> dict:
    """顶栏全局搜索（契约 §4.4）：材料 / 任务 / 场景标签 分组返回。"""
    q = (q or "").strip()
    limit = max(1, min(50, int(limit or 8)))
    if not q:
        return {"materials": [], "tasks": [], "scenes": []}

    _, mats = list_materials(q=q, page=1, page_size=limit)
    tasks = task_repo.list_tasks(status=None, q=q)[:limit]

    # 场景标签：从 material.applications 的 JSON 文本里聚合包含关键词的标签
    scenes: list[str] = []
    rows = query_all(
        "SELECT applications FROM material WHERE archived=0 AND applications LIKE ?", (f"%{q}%",)
    )
    for r in rows:
        for tag in json_loads(r["applications"]) or []:
            if isinstance(tag, str) and q.lower() in tag.lower() and tag not in scenes:
                scenes.append(tag)
        if len(scenes) >= limit:
            break

    return {"materials": mats[:limit], "tasks": tasks, "scenes": scenes[:limit]}
