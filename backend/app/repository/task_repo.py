# -*- coding: utf-8 -*-
"""选型任务 / 会话消息仓储（契约 §4.3、§4.5 `SelectionTask` / `TaskMessage`）。

`task_message.content_json` 存整条消息载荷的 JSON：
- role=user      → {"text": "..."}
- role=assistant → {"text", "constraints", "confidence", "degraded",
                     "results": [...], "relax_note", "reweight_note"}
"""
from __future__ import annotations

from app.core.errors import not_found, validation_error
from app.db.connection import json_dumps, json_loads, now_iso
from app.repository.base import execute, query_all, query_one, rowcount

TASK_STATUS = ("active", "archived")


def _row_to_task(row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "title": d.get("title") or "",
        "pinned": bool(d.get("pinned")),
        "status": d.get("status") or "active",
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
        "recommendation_count": 0,
        "shortlist_count": 0,
    }


def _message_counts(task_ids):
    """批量统计每个任务的消息条数（user/assistant）与待选条数。"""
    if not task_ids:
        return {}, {}
    ph = ",".join("?" * len(task_ids))
    msg = {
        r["task_id"]: r["c"]
        for r in query_all(
            f"SELECT task_id, COUNT(*) AS c FROM task_message WHERE task_id IN ({ph}) "
            "AND role='assistant' GROUP BY task_id",
            list(task_ids),
        )
    }
    sl = {
        r["task_id"]: r["c"]
        for r in query_all(
            f"SELECT task_id, COUNT(*) AS c FROM shortlist_item WHERE task_id IN ({ph}) "
            "GROUP BY task_id",
            list(task_ids),
        )
    }
    return msg, sl


def create(title: str = "") -> dict:
    """新建任务；title 为空时由调用方兜底（首条输入前 12 字）。"""
    ts = now_iso()
    tid = execute(
        "INSERT INTO selection_task(title, pinned, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (title or "新选型任务", 0, "active", ts, ts),
    )
    return get(tid)


def get(task_id: int):
    row = query_one("SELECT * FROM selection_task WHERE id=?", (int(task_id),))
    if row is None:
        return None
    task = _row_to_task(row)
    msg, sl = _message_counts([task_id])
    task["recommendation_count"] = msg.get(task["id"], 0)
    task["shortlist_count"] = sl.get(task["id"], 0)
    return task


def require(task_id: int) -> dict:
    task = get(task_id)
    if task is None:
        raise not_found("选型任务不存在")
    return task


def list_tasks(status: str = None, q: str = None):
    where = ["1=1"]
    params = []
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    elif not status:
        # 默认只返回进行中（归档任务需显式 status=archived|all）
        where.append("status = 'active'")
    if q:
        where.append("title LIKE ?")
        params.append(f"%{q}%")
    sql = (
        "SELECT * FROM selection_task WHERE "
        + " AND ".join(where)
        + " ORDER BY pinned DESC, updated_at DESC, id DESC"
    )
    rows = query_all(sql, params)
    tasks = [_row_to_task(r) for r in rows]
    msg, sl = _message_counts([t["id"] for t in tasks])
    for t in tasks:
        t["recommendation_count"] = msg.get(t["id"], 0)
        t["shortlist_count"] = sl.get(t["id"], 0)
    return tasks


def patch(task_id: int, title=None, pinned=None, status=None) -> dict:
    require(task_id)
    sets = []
    params = []
    if title is not None:
        sets.append("title=?")
        params.append(str(title).strip() or "新选型任务")
    if pinned is not None:
        sets.append("pinned=?")
        params.append(1 if pinned else 0)
    if status is not None:
        if status not in TASK_STATUS:
            raise validation_error("status 仅支持 active / archived")
        sets.append("status=?")
        params.append(status)
        sets.append("archived_at=?")
        params.append(now_iso() if status == "archived" else None)
    if not sets:
        return get(task_id)
    sets.append("updated_at=?")
    params.append(now_iso())
    rowcount(f"UPDATE selection_task SET {', '.join(sets)} WHERE id=?", params + [int(task_id)])
    return get(int(task_id))


def touch(task_id: int) -> None:
    """刷新任务更新时间（新消息 / 待选变更后调用）。"""
    rowcount("UPDATE selection_task SET updated_at=? WHERE id=?", (now_iso(), int(task_id)))


# ---------------- 消息 ----------------
def add_message(task_id: int, role: str, payload: dict) -> dict:
    require(task_id)
    mid = execute(
        "INSERT INTO task_message(task_id, role, content_json, created_at) VALUES (?,?,?,?)",
        (int(task_id), role, json_dumps(payload), now_iso()),
    )
    touch(task_id)
    return get_message(mid)


def _row_to_message(row) -> dict:
    payload = json_loads(row["content_json"])
    if not isinstance(payload, dict):
        payload = {}
    out = {"id": row["id"], "role": row["role"], "created_at": row["created_at"]}
    out.update(payload)
    return out


def get_message(message_id: int):
    row = query_one("SELECT * FROM task_message WHERE id=?", (int(message_id),))
    return _row_to_message(row) if row else None


def list_messages(task_id: int):
    require(task_id)
    rows = query_all(
        "SELECT * FROM task_message WHERE task_id=? ORDER BY id ASC", (int(task_id),)
    )
    return [_row_to_message(r) for r in rows]


def last_assistant_message(task_id: int):
    row = query_one(
        "SELECT * FROM task_message WHERE task_id=? AND role='assistant' ORDER BY id DESC LIMIT 1",
        (int(task_id),),
    )
    return _row_to_message(row) if row else None


def last_user_text(task_id: int):
    row = query_one(
        "SELECT content_json FROM task_message WHERE task_id=? AND role='user' ORDER BY id DESC LIMIT 1",
        (int(task_id),),
    )
    if row is None:
        return ""
    payload = json_loads(row["content_json"])
    return (payload or {}).get("text") or ""


def recent_results(task_id: int):
    """最近一条 assistant 消息的推荐结果（供待选打分 / 回评候选）。"""
    msg = last_assistant_message(task_id)
    if not msg:
        return []
    results = msg.get("results")
    return results if isinstance(results, list) else []
