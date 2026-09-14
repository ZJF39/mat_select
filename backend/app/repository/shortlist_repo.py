# -*- coding: utf-8 -*-
"""待选清单仓储（契约 §4.3、§4.5 `ShortlistItem`）。

约束：`UNIQUE(task_id, material_id)`——同任务同材料只允许一条。
"""
from __future__ import annotations

from app.core.errors import not_found, validation_error
from app.db.connection import now_iso
from app.repository.base import execute, query_all, query_one, rowcount, scalar

VALID_TAGS = ("candidate", "key", "pending", "rejected")


def list_items(task_id: int):
    return [
        dict(r)
        for r in query_all(
            "SELECT * FROM shortlist_item WHERE task_id=? "
            "ORDER BY COALESCE(sort_order, 1000000) ASC, id ASC",
            (int(task_id),),
        )
    ]


def get(item_id: int):
    row = query_one("SELECT * FROM shortlist_item WHERE id=?", (int(item_id),))
    return dict(row) if row else None


def require(item_id: int) -> dict:
    item = get(item_id)
    if item is None:
        raise not_found("待选项不存在")
    return item


def find(task_id: int, material_id: int):
    row = query_one(
        "SELECT * FROM shortlist_item WHERE task_id=? AND material_id=?",
        (int(task_id), int(material_id)),
    )
    return dict(row) if row else None


def next_sort_order(task_id: int) -> int:
    cur = scalar("SELECT MAX(sort_order) FROM shortlist_item WHERE task_id=?", (int(task_id),))
    return int(cur) + 1 if cur is not None else 1


def add(task_id: int, material_id: int, tag: str = None) -> dict:
    if tag and tag not in VALID_TAGS:
        raise validation_error("待选标签仅支持 key / pending / rejected / candidate")
    # 幂等：已存在则直接返回既有条目（不报错、不重复插入）
    exist = find(task_id, material_id)
    if exist:
        return exist
    iid = execute(
        "INSERT INTO shortlist_item(task_id, material_id, user_note, tag, sort_order, added_at) "
        "VALUES (?,?,?,?,?,?)",
        (int(task_id), int(material_id), "", tag or "candidate", next_sort_order(task_id), now_iso()),
    )
    return get(iid)


def patch(item_id: int, user_note=None, tag=None) -> dict:
    require(item_id)
    sets = []
    params = []
    if user_note is not None:
        sets.append("user_note=?")
        params.append(str(user_note))
    if tag is not None:
        if tag not in VALID_TAGS:
            raise validation_error("待选标签仅支持 key / pending / rejected / candidate")
        sets.append("tag=?")
        params.append(tag)
    if sets:
        rowcount(f"UPDATE shortlist_item SET {', '.join(sets)} WHERE id=?", params + [int(item_id)])
    return get(int(item_id))


def set_order(task_id: int, ids) -> None:
    ids = [int(i) for i in (ids or [])]
    for idx, item_id in enumerate(ids, start=1):
        rowcount(
            "UPDATE shortlist_item SET sort_order=? WHERE id=? AND task_id=?",
            (idx, item_id, int(task_id)),
        )


def delete(item_id: int) -> bool:
    require(item_id)
    rowcount("DELETE FROM shortlist_item WHERE id=?", (int(item_id),))
    return True
