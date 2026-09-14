# -*- coding: utf-8 -*-
"""
系统接口验收（docs/plan/02 §4.4）：健康检查 / 全局搜索 / 数据备份。

补齐验收盲区：
- G4：`GET /api/search` 分组检索（材料 / 任务 / 场景标签）此前无自动化用例。
- G6：`POST /api/backup/run` 冷备可用性（备份可独立打开且数据完整）此前无自动化用例。
后端未落地时由 conftest 干净 skip。
"""
import sqlite3
from pathlib import Path


def test_health_reports_material_count(seeded_client):
    """P1 | §4.4 健康检查：返回版本与在用材料数。"""
    r = seeded_client.get("/api/health")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    assert body.get("ok") is True, f"期望 ok，实际 {body}"
    assert body.get("materials", 0) >= 1, f"期望在用材料数≥1，实际 {body.get('materials')}"


def test_global_search_groups_materials_tasks_scenes(seeded_client):
    """P1 | G4 §4.4 全局搜索：按 材料/任务/场景标签 分组返回命中。"""
    task_id = seeded_client.post("/api/tasks", json={"title": "保险丝座选型"}).json()["id"]
    r = seeded_client.get("/api/search", params={"q": "保险丝座"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    for k in ("materials", "tasks", "scenes"):
        assert k in body, f"期望分组含 {k}，实际 {list(body)}"
    # 材料：种子材料（PPS / PA66）在 applications 中标注「保险丝座」，应命中
    assert body["materials"], f"期望命中保险丝座相关材料，实际 {body['materials']}"
    # 任务：标题命中的任务应出现
    assert any(t.get("id") == task_id for t in body["tasks"]), f"期望命中任务，实际 {body['tasks']}"
    # 场景标签：来自 material.applications 的聚合
    assert any("保险丝座" in (s if isinstance(s, str) else s.get("label", "")) for s in body["scenes"]), \
        f"期望命中场景标签，实际 {body['scenes']}"


def test_operation_logs_recorded(seeded_client):
    """P2 | G3 §4.4 操作日志：写操作后可在 /api/logs 查询到留痕（审计）。"""
    seeded_client.post("/api/categories", json={"name": "验收-日志分类", "parent_id": None})
    r = seeded_client.get("/api/logs", params={"limit": 50})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    items = r.json()["items"]
    assert isinstance(items, list) and items, "期望存在操作日志记录"
    assert all({"action", "at"} <= set(it) for it in items), f"日志字段缺失，实际 {items[:2]}"
    assert any(it.get("action") == "新增分类" for it in items), f"期望含「新增分类」日志，实际 {items[:3]}"


def test_global_search_empty_query_returns_empty_groups(seeded_client):
    """P2 | 空查询不报错，返回空分组（避免顶栏空输入触发全表扫描）。"""
    r = seeded_client.get("/api/search", params={"q": ""})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    assert r.json() == {"materials": [], "tasks": [], "scenes": []}, f"期望空分组，实际 {r.json()}"


def test_backup_run_creates_restorable_cold_copy(seeded_client, tmp_db_path, tmp_path, monkeypatch):
    """P0 | G6 数据安全：备份产出可独立打开、含全部在用材料的冷备副本。

    关键点（WAL）：connection.py 启用 journal_mode=WAL，直接复制主库文件会丢失
    尚未 checkpoint 的已提交事务。本用例断言备份库的材料数与在用数严格一致，
    从而覆盖「备份必须是一致快照」这一数据安全不变量。
    """
    import app.core.config as config
    import app.services.settings_service as ss

    # 隔离：备份源=测试库；备份目录=临时目录（不污染 data/backups）
    monkeypatch.setattr(config, "DB_PATH", Path(tmp_db_path))
    monkeypatch.setattr(ss, "BACKUP_DIR", Path(tmp_path) / "backups")

    expected = seeded_client.get("/api/health").json()["materials"]

    r = seeded_client.post("/api/backup/run")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    assert body.get("ok") is True, f"期望 ok=True，实际 {body}"
    dst = Path(body["location"])
    assert dst.exists() and dst.stat().st_size > 0, "期望生成非空备份文件"

    # 冷备可用性：用独立连接打开备份库，材料数须与在用数一致
    con = sqlite3.connect(str(dst))
    try:
        got = con.execute("SELECT COUNT(*) FROM material WHERE archived=0").fetchone()[0]
    finally:
        con.close()
    assert got == expected, \
        f"备份应含 {expected} 条在用材料，实际 {got}（WAL 未落盘会导致偏小）"

    # 备份状态回写最近备份时间
    st = seeded_client.get("/api/backup/status")
    assert st.status_code == 200, f"期望 200，实际 {st.status_code}：{st.text}"
    assert st.json().get("last_backup_at"), f"期望回写 last_backup_at，实际 {st.json()}"


def test_backup_restore_replaces_db_with_snapshot(seeded_client, tmp_db_path, tmp_path, monkeypatch):
    """P0 | G6 备份 → 删库 → 恢复：冷备能将库完整还原为快照那一刻的状态。

    闭环证据（docs/acceptance/00 §3 Gate-2）：
      1) 记录当前在用材料数 N；
      2) `POST /api/backup/run` 生成冷备快照（含 N 条）；
      3) 再写入 1 条材料（N+1）—— 该增量不得出现在快照里；
      4) 关闭单例连接 → 删除在用库（含 -wal/-shm，WAL 残留会污染恢复）→ 用快照覆盖；
      5) 重新经 API 读取：材料数应回到 N，且第 3 步增量不可见。

    第 3~5 步是关键：只有「真正以快照覆盖重建」才能让备份之后的写入消失，
    这区别于「备份文件本身能打开」的弱断言，闭合「备份可用于灾难恢复」。
    """
    import shutil

    import app.core.config as config
    import app.services.settings_service as ss
    from app.db import connection as conn_mod

    monkeypatch.setattr(config, "DB_PATH", Path(tmp_db_path))
    monkeypatch.setattr(ss, "BACKUP_DIR", Path(tmp_path) / "backups")

    live = Path(tmp_db_path)
    n_before = seeded_client.get("/api/health").json()["materials"]

    r = seeded_client.post("/api/backup/run")
    assert r.status_code == 200 and r.json().get("ok") is True, f"备份失败：{r.text}"
    snapshot = Path(r.json()["location"])
    assert snapshot.exists() and snapshot.stat().st_size > 0, "备份文件应存在且非空"

    # 备份之后再写入 1 条：只有「真正恢复」才能让它消失
    extra = {
        "name": "G6恢复校验料-应被回滚", "short_name": "G6-RESTORE",
        "category_id": 2,
        "service_temp_min": -20, "service_temp_max": 120, "service_temp_limit": 120,
        "density_min": 1.0, "density_max": 1.1, "molding_process": ["注塑"],
        "price_min": 10, "price_max": 12, "price_unit": "元/kg",
    }
    cr = seeded_client.post("/api/materials", json=extra)
    assert cr.status_code == 200, f"写入增量材料失败：{cr.text}"
    assert seeded_client.get("/api/health").json()["materials"] == n_before + 1, \
        "前置：备份后写入应使材料数 +1"

    # 删库：必须先关闭单例连接（Windows 会锁定打开中的文件）
    conn_mod.close_conn()
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(live) + suffix)
        if p.exists():
            p.unlink()
    assert not live.exists(), "前置：在用库文件应已删除"

    # 恢复：把冷备快照拷回在用库位置（冷备恢复的标准动作）
    shutil.copyfile(snapshot, live)
    assert live.exists() and live.stat().st_size > 0, "恢复后在用库应存在且非空"

    # 复位连接后经 API 校验
    conn_mod.reset_conn()
    after = seeded_client.get("/api/health")
    assert after.status_code == 200, f"恢复后健康检查失败：{after.text}"
    assert after.json()["materials"] == n_before, \
        f"恢复后应回到快照的 {n_before} 条，实际 {after.json()['materials']}"

    # 备份之后的增量材料必须不可见（证明是「以快照覆盖」，而非「文件恰好在」）
    hit = seeded_client.get("/api/materials", params={"q": "G6恢复校验料-应被回滚"}).json()
    assert hit["total"] == 0, f"增量材料不应存在于快照中，实际命中 {hit['total']} 条"
