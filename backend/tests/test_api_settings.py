# -*- coding: utf-8 -*-
"""
设置 / 系统接口验收（docs/plan/02 §4.4 / §5 / §7；doc/前端原型 10；PRD §3 F2 / §6）

覆盖：推荐权重 GET/PUT（5 维、阈值/上限一致）、负面反馈设置、health、
非功能口径（检索<500ms / 推荐<2s / 首屏<1s，接口层代理测量）。
后端未落地时由 conftest 干净 skip。
"""
import time

import pytest

PENALTY_MAX = 15
THRESHOLD = 2


def test_settings_weights_shape(seeded_client):
    """P0 | 10 屏 权重：GET 返回 5 维 + penalty{threshold,max}，阈值=2 上限≤15。"""
    r = seeded_client.get("/api/settings/weights")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    dims = body.get("dims", [])
    assert len(dims) == 5, f"期望 5 个权重维度，实际 {len(dims)}"
    for d in dims:
        assert {"key", "label", "weight"}.issubset(d.keys()), \
            f"期望维度含 key/label/weight，实际 {d}"
    s = body.get("sum")
    assert s is not None and (abs(s - 100) <= 1 or abs(s - 1.0) <= 0.01), \
        f"期望权重合计≈100(或1.0)，实际 sum={s}"
    pen = body.get("penalty", {})
    assert pen.get("threshold") == THRESHOLD, f"期望 threshold={THRESHOLD}，实际 {pen}"
    assert pen.get("max") <= PENALTY_MAX, f"期望 max≤{PENALTY_MAX}，实际 {pen}"


def test_settings_weights_put_updates(seeded_client):
    """P1 | 10 屏 权重：PUT 修改某维权重后 GET 回显一致，合计仍归一化。"""
    cur = seeded_client.get("/api/settings/weights").json()
    dims = [{"key": d["key"], "weight": d["weight"]} for d in cur["dims"]]
    # 把第一个维度权重调高 5 个百分点（按百分比口径）
    dims[0]["weight"] = (dims[0]["weight"] + 5) if dims[0]["weight"] > 1 else (dims[0]["weight"] + 0.05)
    rp = seeded_client.put("/api/settings/weights", json={"dims": dims})
    assert rp.status_code == 200, f"期望 200，实际 {rp.status_code}：{rp.text}"
    new = rp.json()
    assert new["dims"][0]["weight"] == dims[0]["weight"], "期望回显更新后的权重"
    s = new.get("sum")
    assert abs(s - 100) <= 1 or abs(s - 1.0) <= 0.01, f"PUT 后合计应仍归一化，实际 sum={s}"


def test_settings_feedback_get_delete(seeded_client):
    """P1 | 10 屏 我的负面反馈：GET 返回 items；DELETE 返回 ok（危险操作）。"""
    rg = seeded_client.get("/api/settings/feedback")
    assert rg.status_code == 200, f"期望 200，实际 {rg.status_code}"
    assert "items" in rg.json(), f"期望 items，实际 {rg.json()}"
    rd = seeded_client.delete("/api/settings/feedback")
    assert rd.status_code == 200 and rd.json().get("ok") is True, \
        f"期望 ok，实际 {rd.json()}"


def test_health(seeded_client):
    """P0 | /api/health：ok=true、含 version 与 materials 计数（int）。"""
    r = seeded_client.get("/api/health")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    b = r.json()
    assert b.get("ok") is True, f"期望 ok=true，实际 {b}"
    assert isinstance(b.get("materials"), int), f"期望 materials 为 int，实际 {b}"
    assert b.get("version"), f"期望含 version，实际 {b}"


# ---------------------------------------------------------------------------
# 非功能口径（接口层代理测量；真实阈值见契约 §7）
# ---------------------------------------------------------------------------
def test_perf_search_under_500ms(seeded_client):
    """P0 | §7 检索<500ms：GET /api/materials?q= 接口耗时<0.5s。"""
    t0 = time.perf_counter()
    r = seeded_client.get("/api/materials", params={"q": "PA"})
    dt = time.perf_counter() - t0
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    assert dt < 0.5, f"检索耗时 {dt*1000:.1f}ms 超过 500ms 阈值"


def test_perf_recommend_under_2s(seeded_client):
    """P0 | §7 推荐<2s：/api/recommend/run 接口耗时<2s。"""
    t0 = time.perf_counter()
    r = seeded_client.post("/api/recommend/run",
                            json={"constraints": {"process": "注塑", "temp_limit": 150}})
    dt = time.perf_counter() - t0
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    assert dt < 2.0, f"推荐耗时 {dt*1000:.1f}ms 超过 2s 阈值"


def test_perf_first_screen_under_1s(seeded_client):
    """P1 | §7 首屏<1s（接口层代理）：材料库列表拉取<1s。"""
    t0 = time.perf_counter()
    r = seeded_client.get("/api/materials")
    dt = time.perf_counter() - t0
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    assert dt < 1.0, f"首屏列表耗时 {dt*1000:.1f}ms 超过 1s 阈值"
