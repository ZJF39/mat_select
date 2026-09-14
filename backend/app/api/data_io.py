# -*- coding: utf-8 -*-
"""数据导出 / 导入接口（契约 §4.4，PRD E1/E2）。

导入为两段式：`parse` 只校验并返回预览（**不写库**），`commit` 才按冲突策略写库。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from urllib.parse import quote

from app.core.errors import validation_error
from app.services import io_service

router = APIRouter(tags=["data-io"])


class ExportBody(BaseModel):
    scope: str = "all"
    format: str = "json"
    include_work_data: bool = False
    ids: List[str] = Field(default_factory=list)
    task_id: Optional[int] = None
    dbg: Optional[dict] = None
    q: Optional[str] = None
    category_ids: Optional[str] = None
    processes: Optional[str] = None
    temp_min: Optional[float] = None
    price_max: Optional[float] = None
    flame: Optional[str] = None
    features: Optional[str] = None
    sort: Optional[str] = None
    order: Optional[str] = None


class ImportCommitBody(BaseModel):
    token: str
    conflict_policy: str = "skip"


@router.post("/export")
def export(body: ExportBody):
    dbg = dict(body.dbg or {})
    for k in ("q", "category_ids", "processes", "temp_min", "price_max", "flame",
              "features", "sort", "order"):
        v = getattr(body, k)
        if v is not None:
            dbg.setdefault(k, v)

    filename, blob, media = io_service.export(
        body.scope, body.format, body.include_work_data,
        ids=body.ids, task_id=body.task_id, dbg=dbg,
    )
    ascii_name = filename.encode("ascii", "ignore").decode() or "MatSelect_export"
    return Response(
        content=blob,
        media_type=media,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; "
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.post("/import/parse")
async def import_parse(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise validation_error("文件为空")
    return io_service.import_parse(raw)


@router.post("/import/commit")
def import_commit(body: ImportCommitBody):
    return io_service.import_commit(body.token, body.conflict_policy)
