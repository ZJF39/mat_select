# -*- coding: utf-8 -*-
"""系统接口：健康检查 / 操作日志 / 全局搜索 / 备份状态（契约 §4.4）。"""
from __future__ import annotations

from fastapi import APIRouter

from app.repository.base import scalar
from app.services import material_service, settings_service

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    count = int(scalar("SELECT COUNT(*) FROM material WHERE archived=0") or 0)
    return settings_service.health(count)


@router.get("/logs")
def logs(limit: int = 50):
    return {"items": settings_service.list_logs(limit)}


@router.get("/search")
def search(q: str = "", limit: int = 8):
    return material_service.global_search(q, limit)


@router.get("/backup/status")
def backup_status():
    return settings_service.backup_status()


@router.post("/backup/run")
def backup_run():
    return settings_service.run_backup()
