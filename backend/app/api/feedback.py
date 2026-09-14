# -*- coding: utf-8 -*-
"""回评接口（契约 §4.3、PRD C1）。

`fail` 必须带理由；后端做语义拆解：命中具体材料 → `material_negative_feedback`；
未命中 → `requirement_gap`（知识盲区）。拆解结果**只作为反馈标签记录，不直接改写推荐规则**。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import workbench_service

router = APIRouter(tags=["feedback"])


class FeedbackBody(BaseModel):
    result: str  # success | fail | skipped
    reason_text: Optional[str] = None
    reason_tags: List[str] = Field(default_factory=list)
    material_uids: List[str] = Field(default_factory=list)


@router.post("/tasks/{task_id}/feedback")
def submit_feedback(task_id: int, body: FeedbackBody):
    return workbench_service.submit_feedback(task_id, body.model_dump())


@router.get("/tasks/{task_id}/feedback")
def get_feedback(task_id: int):
    return workbench_service.get_task_feedback(task_id)
