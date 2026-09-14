# -*- coding: utf-8 -*-
"""智能推荐接口（契约 §4.2）。

`parse` 与 `run` **必须拆成两个接口**：用户要先确认约束标签、
确认后才跑硬约束过滤（PRD B1「结构化解析确认」，原型 05 §1.1「③→④ 之间不允许出结果」）。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.repository import task_repo
from app.services import recommend_service

router = APIRouter(prefix="/recommend", tags=["recommend"])


class ParseBody(BaseModel):
    text: str = ""
    task_id: Optional[int] = None


class ConstraintsBody(BaseModel):
    part_type: Optional[str] = None
    process: Optional[str] = None
    temp_limit: Optional[float] = None
    extra: List[str] = Field(default_factory=list)


class RunBody(BaseModel):
    constraints: ConstraintsBody
    task_id: Optional[int] = None


@router.post("/parse")
def parse(body: ParseBody):
    """第 1 段：约束抽取（词典 + 正则）。不返回任何推荐结果。"""
    return recommend_service.parse(body.text, task_id=body.task_id)


@router.post("/run")
def run(body: RunBody):
    """第 ②③④ 段：硬约束过滤 → 加权排序 → 模板解释。

    硬约束不可突破；为空则先放宽温度 10 °C，仍为空返回空列表 + degraded（由前端展示优化提示）。
    """
    user_text = ""
    if body.task_id:
        task_repo.require(int(body.task_id))
        user_text = task_repo.last_user_text(int(body.task_id))
    return recommend_service.run(
        body.constraints.model_dump(), task_id=body.task_id, user_text=user_text
    )
