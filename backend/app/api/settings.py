# -*- coding: utf-8 -*-
"""设置接口：推荐权重 / 我的负面反馈（契约 §4.4、原型 02 §10）。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import settings_service, workbench_service

router = APIRouter(prefix="/settings", tags=["settings"])


class WeightUpdateItem(BaseModel):
    key: str
    weight: float


class PenaltyBody(BaseModel):
    threshold: int = 2
    max: int = 15


class WeightsUpdateBody(BaseModel):
    dims: List[WeightUpdateItem] = Field(default_factory=list)
    penalty: Optional[PenaltyBody] = None


@router.get("/weights")
def get_weights():
    return settings_service.get_weights()


@router.put("/weights")
def save_weights(body: WeightsUpdateBody):
    return settings_service.save_weights(
        [d.model_dump() for d in body.dims],
        body.penalty.model_dump() if body.penalty else None,
    )


@router.get("/feedback")
def list_my_feedback():
    return {"items": workbench_service.list_my_feedback()}


@router.delete("/feedback")
def clear_my_feedback():
    return workbench_service.clear_my_feedback()
