# -*- coding: utf-8 -*-
"""选型任务 / 会话接口（契约 §4.3）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import workbench_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreateBody(BaseModel):
    title: Optional[str] = None


class TaskPatchBody(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    status: Optional[str] = None


class MessageCreateBody(BaseModel):
    text: str = ""


@router.get("")
def list_tasks(status: Optional[str] = None, q: Optional[str] = None):
    return {"items": workbench_service.list_tasks(status=status, q=q)}


@router.post("")
def create_task(body: TaskCreateBody = None):
    return workbench_service.create_task((body.title if body else None))


@router.patch("/{task_id}")
def patch_task(task_id: int, body: TaskPatchBody):
    return workbench_service.patch_task(
        task_id, title=body.title, pinned=body.pinned, status=body.status
    )


@router.get("/{task_id}/messages")
def list_messages(task_id: int):
    return {"items": workbench_service.list_messages(task_id)}


@router.post("/{task_id}/messages")
def send_message(task_id: int, body: MessageCreateBody):
    """追问 / 首次输入：写入用户消息 + assistant 消息（含约束回显与推荐结果）。"""
    return workbench_service.send_message(task_id, body.text)
