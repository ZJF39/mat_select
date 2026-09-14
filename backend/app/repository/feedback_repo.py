# -*- coding: utf-8 -*-
"""回评仓储（契约 §4.3 / §5.2）。

三张表分工：
- `recommendation_feedback`       一次回评（success / fail / skipped）
- `material_negative_feedback`    命中材料后的**按维度**负面反馈（active=1 才参与降权）
- `requirement_gap`               未命中任何材料 → 知识盲区
"""
from __future__ import annotations

from app.db.connection import json_dumps, json_loads, now_iso
from app.repository.base import execute, query_all, query_one, rowcount, scalar


# ---------------- 回评主体 ----------------
def insert_feedback(task_id: int, result: str, reason_text, reason_tags, parsed: dict) -> int:
    return execute(
        "INSERT INTO recommendation_feedback(task_id, result, reason_text, reason_tags, "
        "parsed_reason, created_at) VALUES (?,?,?,?,?,?)",
        (
            int(task_id) if task_id else None,
            result,
            reason_text,
            json_dumps(reason_tags or []),
            json_dumps(parsed or {}),
            now_iso(),
        ),
    )


def _row_to_feedback(row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "task_id": d.get("task_id"),
        "result": d.get("result"),
        "reason_text": d.get("reason_text"),
        "reason_tags": json_loads(d.get("reason_tags")),
        "parsed": json_loads(d.get("parsed_reason")),
        "created_at": d.get("created_at"),
    }


def latest_feedback(task_id: int):
    row = query_one(
        "SELECT * FROM recommendation_feedback WHERE task_id=? ORDER BY id DESC LIMIT 1",
        (int(task_id),),
    )
    return _row_to_feedback(row) if row else None


def list_feedback(limit: int = 100):
    rows = query_all(
        "SELECT * FROM recommendation_feedback ORDER BY id DESC LIMIT ?", (int(limit),)
    )
    return [_row_to_feedback(r) for r in rows]


# ---------------- 负面反馈（降权数据源） ----------------
def insert_negative(material_id: int, dimension: str, reason: str, source_feedback_id=None,
                    weight: float = 1.0) -> int:
    return execute(
        "INSERT INTO material_negative_feedback(material_id, dimension, reason, "
        "source_feedback_id, weight, active, created_at) VALUES (?,?,?,?,?,1,?)",
        (int(material_id), dimension, reason, source_feedback_id, float(weight), now_iso()),
    )


def hits_by_material(material_id: int) -> dict:
    """该材料按维度聚合的 active 命中次数。"""
    rows = query_all(
        "SELECT dimension, COUNT(*) AS c FROM material_negative_feedback "
        "WHERE material_id=? AND active=1 GROUP BY dimension",
        (int(material_id),),
    )
    return {r["dimension"]: r["c"] for r in rows}


def hits_for_materials(material_ids) -> dict:
    """批量：{material_id: {dimension: count}}，一次查询避免 N+1。"""
    ids = [int(i) for i in (material_ids or [])]
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    out = {}
    for r in query_all(
        f"SELECT material_id, dimension, COUNT(*) AS c FROM material_negative_feedback "
        f"WHERE active=1 AND material_id IN ({ph}) GROUP BY material_id, dimension",
        ids,
    ):
        out.setdefault(r["material_id"], {})[r["dimension"]] = r["c"]
    return out


def delete_negative_by_material(material_id: int) -> int:
    return rowcount("DELETE FROM material_negative_feedback WHERE material_id=?", (int(material_id),))


def clear_negative() -> int:
    return rowcount("DELETE FROM material_negative_feedback")


def list_negative_settings(only_active: bool = True):
    """设置页「我的负面反馈」：材料 + 维度 + 命中次数 + 生效状态。"""
    where = "WHERE n.active=1" if only_active else ""
    rows = query_all(
        "SELECT n.material_id, m.uid AS material_uid, m.name AS material_name, "
        "       n.dimension, COUNT(*) AS hit_count, MAX(n.active) AS active, "
        "       MAX(n.created_at) AS last_at "
        f"FROM material_negative_feedback n LEFT JOIN material m ON m.id = n.material_id "
        f"{where} GROUP BY n.material_id, n.dimension ORDER BY hit_count DESC, n.material_id"
    )
    out = []
    for r in rows:
        out.append(
            {
                "material_uid": r["material_uid"],
                "material_name": r["material_name"],
                "dimension": r["dimension"],
                "hit_count": r["hit_count"],
                "active": bool(r["active"]),
                "last_at": r["last_at"],
            }
        )
    return out


# ---------------- 知识盲区 ----------------
def insert_gap(task_id: int, reason_text: str, parsed: dict) -> int:
    return execute(
        "INSERT INTO requirement_gap(task_id, reason_text, parsed_reason, resolved, created_at) "
        "VALUES (?,?,?,0,?)",
        (int(task_id) if task_id else None, reason_text, json_dumps(parsed or {}), now_iso()),
    )


def list_gaps(since_iso: str = None):
    if since_iso:
        rows = query_all(
            "SELECT * FROM requirement_gap WHERE created_at >= ? ORDER BY id DESC", (since_iso,)
        )
    else:
        rows = query_all("SELECT * FROM requirement_gap ORDER BY id DESC")
    out = []
    for r in rows:
        d = dict(r)
        d["parsed"] = json_loads(d.get("parsed_reason"))
        out.append(d)
    return out


def count_gaps() -> int:
    return int(scalar("SELECT COUNT(*) FROM requirement_gap") or 0)
