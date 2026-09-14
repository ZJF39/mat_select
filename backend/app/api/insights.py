# -*- coding: utf-8 -*-
"""知识盲区报告接口（契约 §4.4、PRD C1 第 4 步「知识盲区报告」）。"""
from __future__ import annotations

from fastapi import APIRouter

from app.services import workbench_service

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/gaps")
def gaps(range: str = "week"):
    """高频缺口维度 + 建议动作，用于指导补数据 / 补词典。"""
    return {"items": workbench_service.gaps(range)}
