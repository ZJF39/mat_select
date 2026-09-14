# -*- coding: utf-8 -*-
"""材料接口（契约 §4.1）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.services import material_service

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("")
def list_materials(
    q: Optional[str] = None,
    category_ids: Optional[str] = None,
    processes: Optional[str] = None,
    temp_min: Optional[float] = None,
    price_max: Optional[float] = None,
    flame: Optional[str] = None,
    features: Optional[str] = None,
    sort: str = "updated_at",
    order: str = "desc",
    archived: int = 0,
    page: int = 1,
    page_size: int = 20,
    include_archived: int = Query(0, alias="includeArchived"),
):
    """列表 / 精确检索。条件之间为 AND 交集（PRD A1/A3）。"""
    if include_archived:
        archived = 1
    total, items = material_service.list_materials(
        q=q, category_ids=category_ids, processes=processes, temp_min=temp_min,
        price_max=price_max, flame=flame, features=features, sort=sort, order=order,
        archived=archived, page=page, page_size=page_size,
    )
    return {"total": total, "items": items}


@router.get("/{uid}")
def get_material(uid: str):
    return material_service.get_detail(uid)


@router.post("")
def create_material(body: dict):
    return material_service.create_material(body)


@router.put("/{uid}")
def update_material(uid: str, body: dict):
    material, new_version = material_service.update_material(uid, body)
    return {"material": material, "new_version": new_version}


@router.delete("/{uid}")
def archive_material(uid: str):
    """归档（只归档不删除，PRD Q7）。"""
    return material_service.archive_material(uid)


@router.get("/{uid}/revisions")
def list_revisions(uid: str):
    return {"items": material_service.list_revisions(uid)}


@router.get("/{uid}/revisions/{a}/diff")
def diff_revisions(uid: str, a: int, against: Optional[int] = None):
    return material_service.diff(uid, a, against)


@router.post("/{uid}/revisions/{rid}/restore")
def restore_revision(uid: str, rid: int):
    material, new_version = material_service.restore(uid, rid)
    return {"material": material, "new_version": new_version}


@router.get("/{uid}/feedback")
def material_feedback(uid: str):
    return {"items": material_service.material_feedback(uid)}


@router.delete("/{uid}/feedback")
def clear_material_feedback(uid: str):
    return material_service.clear_material_feedback(uid)
