# -*- coding: utf-8 -*-
"""分类体系接口（契约 §4.1）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import material_service

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryCreateBody(BaseModel):
    name: str
    parent_id: Optional[int] = None


class CategoryPatchBody(BaseModel):
    name: str


@router.get("")
def list_categories():
    return {"items": material_service.category_tree()}


@router.post("", status_code=201)
def create_category(body: CategoryCreateBody):
    return material_service.create_category(body.name, body.parent_id)


@router.patch("/{cid}")
def patch_category(cid: int, body: CategoryPatchBody):
    return material_service.patch_category(cid, body.name)


@router.delete("/{cid}")
def delete_category(cid: int):
    return material_service.delete_category(cid)
