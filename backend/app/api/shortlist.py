# -*- coding: utf-8 -*-
"""待选材料清单接口（契约 §4.3、PRD B6）。

同一任务内同一材料**不重复入待选**（DB 层 `UNIQUE(task_id, material_id)`），
服务层对重复加入是幂等的（返回既有条目而不是报错），前端据此显示「已在待选」。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import workbench_service

router = APIRouter(tags=["shortlist"])


class ShortlistAddBody(BaseModel):
    material_uid: str
    tag: Optional[str] = "candidate"


class ShortlistPatchBody(BaseModel):
    user_note: Optional[str] = None
    tag: Optional[str] = None


class ShortlistOrderBody(BaseModel):
    ids: List[int] = Field(default_factory=list)


@router.get("/tasks/{task_id}/shortlist")
def list_shortlist(task_id: int):
    return {"items": workbench_service.list_shortlist(task_id)}


@router.post("/tasks/{task_id}/shortlist")
def add_shortlist(task_id: int, body: ShortlistAddBody):
    return workbench_service.add_shortlist(task_id, body.material_uid, body.tag)


@router.put("/tasks/{task_id}/shortlist/order")
def reorder_shortlist(task_id: int, body: ShortlistOrderBody):
    return {"items": workbench_service.reorder_shortlist(task_id, body.ids)}


@router.patch("/shortlist/{item_id}")
def patch_shortlist(item_id: int, body: ShortlistPatchBody):
    return workbench_service.patch_shortlist(item_id, body.user_note, body.tag)


@router.delete("/shortlist/{item_id}")
def remove_shortlist(item_id: int):
    return workbench_service.remove_shortlist(item_id)
