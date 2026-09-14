# -*- coding: utf-8 -*-
"""
真实规模性能基线（docs/plan/00 §8.2 性能口径 / §M3·M4 DoD）

为什么单独建文件：
    test_api_settings.py 中的三条 perf 用例运行在**受控种子 8 条**规模上，
    耗时 <5ms，可以证明「逻辑不慢」，但**不能**证明 §8.2 的口径
    （检索 <500ms / 首屏 <1s 明确要求 **200 条规模**）。
    本文件构造 200 条规模的真实数据集，按 p95 判定口径，避免用 8 条数据
    冒充 200 条规模的达标结论。

隔离策略：使用**独立的临时库文件**，不污染 conftest 的 session 临时库
（否则会破坏 seeded_client 的「材料总数 == 8」这类计数断言）。
本文件按字母序最后执行，且 fixture 结束后还原 MATSELECT_DB 环境变量。

本文件属于验收专家（backend/tests/**），不改生产代码。
"""

import copy
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from conftest import (  # noqa: E402
    INIT_DB,
    SEED_CATEGORIES,
    SEED_MATERIALS,
)

# ---- §8.2 口径阈值（毫秒）----
TH_SEARCH_MS = 500.0      # 检索响应
TH_RECOMMEND_MS = 2000.0  # 推荐响应
TH_FIRST_SCREEN_MS = 1000.0  # 材料库首屏

SCALE_N = 200   # §8.2「200 条规模」
ROUNDS = 20     # 每口径重复次数（推荐较重，单独降轮次）


def _pctl(sorted_ms, q):
    """简单分位数（nearest-rank，样本量小，不引入 numpy 依赖）。"""
    if not sorted_ms:
        return float("nan")
    idx = min(len(sorted_ms) - 1, max(0, int(round(q * (len(sorted_ms) - 1)))))
    return sorted_ms[idx]


def _measure(fn, rounds):
    """重复调用并返回 (p50, p95, max, 样本数)，全部断言 200。"""
    xs = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        r = fn()
        xs.append((time.perf_counter() - t0) * 1000.0)
        assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text[:200]}"
    xs.sort()
    return _pctl(xs, 0.50), _pctl(xs, 0.95), xs[-1], len(xs)


def _seed_scale(client, n):
    """写入 4 分类 + n 条材料（克隆受控种子并做唯一化与参数扰动）。"""
    cat_ids = {}
    for cat in SEED_CATEGORIES:
        r = client.post("/api/categories", json=cat)
        if r.status_code == 200:
            cat_ids[cat["name"]] = r.json().get("id")
    if len(cat_ids) < len(SEED_CATEGORIES):
        r = client.get("/api/categories")
        if r.status_code == 200:
            for node in r.json().get("items", []):
                cat_ids.setdefault(node["name"], node["id"])
                for child in node.get("children", []) or []:
                    cat_ids.setdefault(child["name"], child["id"])

    for i in range(n):
        base = SEED_MATERIALS[i % len(SEED_MATERIALS)]
        body = copy.deepcopy(base)
        tag = f"{i:03d}"
        body["short_name"] = f'{base["short_name"]}-{tag}'
        body["name"] = f'{base["name"]} 规格{tag}'
        body["aliases"] = list(base.get("aliases", [])) + [f'X{tag}']
        # 参数扰动：制造有区分度的区间分布，让「区间 WHERE + FTS5 + 加权排序」都真实受压
        body["density_min"] = round(base["density_min"] + (i % 7) * 0.01, 3)
        body["density_max"] = round(base["density_max"] + (i % 7) * 0.01, 3)
        body["price_min"] = base["price_min"] + (i % 11)
        body["price_max"] = base["price_max"] + (i % 11)
        body["service_temp_limit"] = base["service_temp_limit"] - (i % 5) * 5
        cid = base.get("category_id")
        if cid is not None and cid <= len(SEED_CATEGORIES):
            body["category_id"] = cat_ids.get(SEED_CATEGORIES[cid - 1]["name"], cid)
        r = client.post("/api/materials", json=body)
        assert r.status_code == 200, f"第 {i} 条材料写入失败：{r.status_code} {r.text[:200]}"


@pytest.fixture(scope="module")
def scale_client(backend_app):
    """独立临时库 + 200 条规模数据集的 TestClient。"""
    prev = os.environ.get("MATSELECT_DB")
    fd, path = tempfile.mkstemp(prefix="matselect_scale_", suffix=".db")
    os.close(fd)
    os.remove(path)
    os.environ["MATSELECT_DB"] = path
    if INIT_DB is not None:
        INIT_DB()
    with TestClient(backend_app) as c:
        _seed_scale(c, SCALE_N)
        yield c
    if prev is None:
        os.environ.pop("MATSELECT_DB", None)
    else:
        os.environ["MATSELECT_DB"] = prev
    try:
        os.remove(path)
    except OSError:
        pass


def test_scale_dataset_actually_200(scale_client):
    """P0 | 前置守卫：数据集必须真的是 200 条，否则性能结论无效。"""
    r = scale_client.get("/api/materials", params={"page_size": 1})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    total = r.json().get("total")
    assert total == SCALE_N, f"期望 {SCALE_N} 条规模数据集，实际 total={total}"


def test_scale_perf_search_under_500ms(scale_client):
    """P0 | §8.2 检索 <500ms（200 条规模，FTS5 + 区间 WHERE）。"""
    p50, p95, mx, n = _measure(
        lambda: scale_client.get("/api/materials", params={"q": "PA"}), ROUNDS
    )
    print(f"\n[perf-scale] 检索  200条 q=PA      n={n} p50={p50:.1f}ms p95={p95:.1f}ms max={mx:.1f}ms 阈值<{TH_SEARCH_MS:.0f}ms")
    assert p95 < TH_SEARCH_MS, f"检索 p95={p95:.1f}ms 超过 {TH_SEARCH_MS:.0f}ms"


def test_scale_perf_first_screen_under_1s(scale_client):
    """P1 | §8.2 材料库首屏 <1s（200 条，列表拉取）。"""
    p50, p95, mx, n = _measure(
        lambda: scale_client.get("/api/materials", params={"page_size": 24}), ROUNDS
    )
    print(f"[perf-scale] 首屏  200条 page=24   n={n} p50={p50:.1f}ms p95={p95:.1f}ms max={mx:.1f}ms 阈值<{TH_FIRST_SCREEN_MS:.0f}ms")
    assert p95 < TH_FIRST_SCREEN_MS, f"首屏 p95={p95:.1f}ms 超过 {TH_FIRST_SCREEN_MS:.0f}ms"


def test_scale_perf_recommend_under_2s(scale_client):
    """P0 | §8.2 推荐 <2s（200 条规模，约束抽取 + 硬过滤 + 加权排序 + 解释生成）。"""
    payload = {"constraints": {"process": "注塑", "temp_limit": 150}}
    p50, p95, mx, n = _measure(
        lambda: scale_client.post("/api/recommend/run", json=payload), ROUNDS // 2
    )
    print(f"[perf-scale] 推荐  200条 注塑/150  n={n} p50={p50:.1f}ms p95={p95:.1f}ms max={mx:.1f}ms 阈值<{TH_RECOMMEND_MS:.0f}ms")
    assert p95 < TH_RECOMMEND_MS, f"推荐 p95={p95:.1f}ms 超过 {TH_RECOMMEND_MS:.0f}ms"
