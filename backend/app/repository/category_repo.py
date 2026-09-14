"""分类仓储（契约 §4.1）。两级分类树，含每节点材料计数。"""
from __future__ import annotations

from app.db.connection import now_iso
from app.repository.base import execute, query_all, query_one, scalar

from app.core.errors import conflict, not_found, validation_error


def list_tree():
    rows = query_all(
        "SELECT id, name, parent_id, sort_order, created_at FROM category ORDER BY parent_id, sort_order, id"
    )
    nodes = {r["id"]: dict(r) for r in rows}
    counts = {
        r["category_id"]: r["c"]
        for r in query_all(
            "SELECT category_id, COUNT(*) AS c FROM material WHERE archived=0 GROUP BY category_id"
        )
    }

    def build(pid):
        children = []
        for nid, n in nodes.items():
            if n["parent_id"] == pid:
                node = {
                    "id": n["id"],
                    "name": n["name"],
                    "parent_id": n["parent_id"],
                    "sort_order": n["sort_order"],
                    "created_at": n["created_at"],
                    "count": counts.get(n["id"], 0),
                    "children": build(n["id"]),
                }
                children.append(node)
        children.sort(key=lambda x: (x["sort_order"], x["id"]))
        return children

    return build(None)


def create(name: str, parent_id=None):
    if not name or not name.strip():
        raise validation_error("分类名称不能为空")
    pid = int(parent_id) if parent_id else None
    if pid is not None and scalar("SELECT id FROM category WHERE id=?", (pid,)) is None:
        raise not_found("父分类不存在")
    return execute(
        "INSERT INTO category(name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
        (name.strip(), pid, 0, now_iso()),
    )


def patch(cid: int, name: str):
    if scalar("SELECT id FROM category WHERE id=?", (cid,)) is None:
        raise not_found("分类不存在")
    execute("UPDATE category SET name=? WHERE id=?", (name.strip(), cid))
    return True


def delete(cid: int):
    if scalar("SELECT id FROM category WHERE id=?", (cid,)) is None:
        raise not_found("分类不存在")
    if scalar("SELECT COUNT(*) FROM material WHERE category_id=?", (cid,)) > 0:
        raise conflict("该分类下仍有材料引用，无法删除")
    # 子分类提升为顶级
    execute("UPDATE category SET parent_id=NULL WHERE parent_id=?", (cid,))
    execute("DELETE FROM category WHERE id=?", (cid,))
    return True
