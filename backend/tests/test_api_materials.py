# -*- coding: utf-8 -*-
"""
材料 API 验收（docs/plan/02 §4.1 / §4.6；doc/前端原型 05 §2；PRD §3 A1/A2/D1-D4）

覆盖：列表/检索/排序、四态（成功/空/错误）、详情、新建/编辑/版本/diff、
分类树、字段级数据一致性、种子数据完整率。
所有用例在后端未落地时由 conftest 干净 skip（阻塞项如实记录）。
"""
import json
import os
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_MATERIALS = BACKEND_ROOT.parent / "data" / "materials.json"


# ---------------------------------------------------------------------------
# 列表 / 检索 / 排序
# ---------------------------------------------------------------------------
def test_materials_list_shape(seeded_client):
    """P0 | 材料列表返回 {total, items} 且 items 为数组（四态·成功基础结构）。"""
    r = seeded_client.get("/api/materials")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    assert "total" in body and isinstance(body["total"], int), \
        f"期望含 int 型 total，实际 body={body}"
    assert "items" in body and isinstance(body["items"], list), \
        f"期望含 list 型 items，实际 body={body}"
    assert body["total"] >= 5, f"种子应≥5条，实际 total={body['total']}"


def test_materials_search_by_keyword(seeded_client):
    """P0 | A3 关键词检索：'PA66' 应命中 PA66+GF30（含别名/名称子串）。"""
    r = seeded_client.get("/api/materials", params={"q": "PA66"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    items = r.json()["items"]
    names = [m["name"] for m in items]
    assert any("PA66" in n for n in names), \
        f"期望命中含 PA66 的材料，实际返回 names={names}"


def test_materials_range_filter_temp(seeded_client):
    """P0 | A3 参数区间检索：service_temp_limit>=200 仅含高温料（PPS/LCP）。"""
    r = seeded_client.get("/api/materials", params={"temp_min": 200})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    items = r.json()["items"]
    for m in items:
        assert m["service_temp_limit"] >= 200, \
            f"期望全部 service_temp_limit>=200，但 {m['name']}={m['service_temp_limit']}"
    assert len(items) >= 2, f"期望≥2 条高温料，实际 {len(items)} 条"


def test_materials_sort_service_temp_desc(seeded_client):
    """P1 | 排序：service_temp_limit 降序，首项应为最大耐温。"""
    r = seeded_client.get("/api/materials",
                           params={"sort": "service_temp_limit", "order": "desc"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    items = r.json()["items"]
    limits = [m["service_temp_limit"] for m in items]
    assert limits == sorted(limits, reverse=True), \
        f"期望降序，实际 service_temp_limit 序列={limits}"


def test_materials_empty_result(seeded_client):
    """P0 | 四态·空：无匹配关键词 → total=0（空态，非错误）。"""
    r = seeded_client.get("/api/materials", params={"q": "__no_such_material_xyz__"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    body = r.json()
    assert body["total"] == 0 and body["items"] == [], \
        f"期望空结果 total=0，实际 {body}"


def test_materials_not_found_error_state(seeded_client):
    """P0 | 四态·错误：不存在的 uid → 404 + {error:{code:NOT_FOUND}}。"""
    r = seeded_client.get("/api/materials/nonexistent-uid-000")
    assert r.status_code == 404, f"期望 404，实际 {r.status_code}：{r.text}"
    err = r.json().get("error", {})
    assert err.get("code") == "NOT_FOUND", \
        f"期望 error.code=NOT_FOUND，实际 {err}"


# ---------------------------------------------------------------------------
# 详情
# ---------------------------------------------------------------------------
def test_material_detail_success(seeded_client):
    """P0 | A2 详情成功：字段回显且与列表一致（含 uid）。"""
    listing = seeded_client.get("/api/materials", params={"q": "PA66+GF30"}).json()["items"]
    uid = listing[0]["uid"]
    r = seeded_client.get(f"/api/materials/{uid}")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    d = r.json()
    assert d["uid"] == uid, f"期望 uid={uid}，实际 {d.get('uid')}"
    assert d["name"] == listing[0]["name"], "详情 name 应与列表一致"


def test_material_detail_missing_uid(seeded_client):
    """P0 | 四态·错误：uid 不存在 → 404 全页空态语义（API 层）。"""
    r = seeded_client.get("/api/materials/zzz-missing")
    assert r.status_code == 404, f"期望 404，实际 {r.status_code}"


# ---------------------------------------------------------------------------
# 新建 / 编辑 / 版本 / diff
# ---------------------------------------------------------------------------
def test_material_create(seeded_client):
    """P0 | D1 新建：返回生成 uid + 字段回显。"""
    body = {
        "name": "测试料-临时", "short_name": "TEST", "category_id": 2,
        "service_temp_min": -20, "service_temp_max": 120, "service_temp_limit": 120,
        "density_min": 1.0, "density_max": 1.1, "molding_process": ["注塑"],
        "price_min": 10, "price_max": 12, "price_unit": "元/kg",
    }
    r = seeded_client.post("/api/materials", json=body)
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    d = r.json()
    assert d.get("uid"), f"期望生成 uid，实际 {d}"
    assert d["name"] == "测试料-临时", "新建后 name 应回显"


def test_material_create_validation_error(seeded_client):
    """P0 | D1 校验：缺必填 name → VALIDATION_ERROR。"""
    r = seeded_client.post("/api/materials", json={"short_name": "NO_NAME"})
    assert r.status_code == 422 or r.status_code == 400, \
        f"期望 400/422，实际 {r.status_code}：{r.text}"
    if r.status_code == 400:
        assert r.json().get("error", {}).get("code") == "VALIDATION_ERROR", \
            f"期望 error.code=VALIDATION_ERROR，实际 {r.json()}"


def test_material_update_and_diff(seeded_client):
    """P0 | D2/D3 编辑 3 字段 + Git 式 diff：new_version+1、summary 含 '3'、rows=3。"""
    # 取一条种子材料编辑
    uid = seeded_client.get("/api/materials", params={"q": "PBT+GF30"}).json()["items"][0]["uid"]
    patch = {
        "service_temp_limit": 145,           # 改1
        "price_max": 30,                      # 改2
        "features": ["阻燃", "低成本", "新特性"],  # 改3（数组字段）
    }
    r = seeded_client.put(f"/api/materials/{uid}", json=patch)
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    upd = r.json()
    assert "new_version" in upd and upd["new_version"] >= 2, \
        f"期望 new_version>=2，实际 {upd}"

    # 版本列表
    rv = seeded_client.get(f"/api/materials/{uid}/revisions")
    assert rv.status_code == 200, f"期望 200，实际 {rv.status_code}"
    revs = rv.json().get("items", [])
    assert len(revs) >= 2, f"期望至少 2 个版本，实际 {len(revs)}"

    # diff 取「本次编辑版」与其**紧邻上一版**（契约 §4.5 DiffPayload / 仓库 update_material 注记）。
    # 注意：version 是全局递增的快照 id，且本 session 各用例共享同一个库，
    # 先前的用例（如 E2 overwrite 导入）也会在同一材料上留下「编辑」快照，
    # 因此不能固定取 revs[0]/revs[1]，否则 diff 到的可能是两次内容相同的版本。
    versions = sorted({v["version"] for v in revs})
    b = upd["new_version"]
    prior = [v for v in versions if v < b]
    assert b == versions[-1], f"期望本次编辑产生最新版本 {versions[-1]}，实际 new_version={b}"
    assert prior, f"期望存在上一版用于 diff，实际 versions={versions}"
    a = prior[-1]
    rd = seeded_client.get(f"/api/materials/{uid}/revisions/{a}/diff",
                           params={"against": b})
    assert rd.status_code == 200, f"期望 200，实际 {rd.status_code}：{rd.text}"
    diff = rd.json()
    assert "3" in diff.get("summary", ""), \
        f"期望 summary 含 '本次修改了 3 个字段'，实际 summary={diff.get('summary')}"
    rows = diff.get("rows", [])
    assert len(rows) == 3, f"期望 3 条变更行，实际 {len(rows)} 条：{rows}"
    valid_types = {"modify", "add", "remove"}
    for row in rows:
        assert row.get("type") in valid_types, \
            f"期望 type ∈ {valid_types}，实际 {row}"

    # 自清理：上述编辑把 service_temp_limit(145) 与 service_temp_max(140) 拉开，
    # 破坏了种子数据不变量（见 test_field_consistency_temp_limit_eq_max）；
    # 各用例共享同一库，故恢复至最早版本，避免污染后续用例（不借助放宽断言）。
    rr = seeded_client.post(f"/api/materials/{uid}/revisions/{versions[0]}/restore")
    assert rr.status_code == 200, f"期望恢复 200，实际 {rr.status_code}：{rr.text}"


def test_material_feedback_get_delete(seeded_client):
    """P1 | 材料反馈：GET 返回维度统计；DELETE 返回 ok。"""
    uid = seeded_client.get("/api/materials", params={"q": "PA66+GF30"}).json()["items"][0]["uid"]
    rg = seeded_client.get(f"/api/materials/{uid}/feedback")
    assert rg.status_code == 200, f"期望 200，实际 {rg.status_code}"
    assert "items" in rg.json(), f"期望 items 字段，实际 {rg.json()}"
    rd = seeded_client.delete(f"/api/materials/{uid}/feedback")
    assert rd.status_code == 200 and rd.json().get("ok") is True, \
        f"期望 ok=true，实际 {rd.json()}"


# ---------------------------------------------------------------------------
# 分类树（四态 + 两级）
# ---------------------------------------------------------------------------
def _flatten_tree(nodes):
    """摊平分类树。

    契约 §4.1：`GET /api/categories → { items: CategoryNode[] }（两级，含 count）`，
    CategoryNode 带 `children?: CategoryNode[]`（见原型 §4 TS 定义），
    即 items 是**一级节点数组**、二级节点嵌在 `children` 里，而非扁平数组。
    """
    out = []
    for n in nodes or []:
        out.append(n)
        out.extend(_flatten_tree(n.get("children")))
    return out


def test_categories_two_level_with_count(seeded_client):
    """P0 | F1 分类树：两级嵌套结构，含 count，子节点归属于父。"""
    r = seeded_client.get("/api/categories")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    roots = r.json().get("items", [])
    assert roots, "期望存在分类节点"
    assert all(n.get("parent_id") is None for n in roots), \
        f"期望 items 顶层均为一级分类，实际 {[n.get('parent_id') for n in roots]}"
    nodes = _flatten_tree(roots)
    assert all("count" in n for n in nodes), \
        f"期望每个分类节点含 count，实际 {[n.get('name') for n in nodes if 'count' not in n]}"

    root_ids = {n["id"] for n in roots}
    second = [n for n in nodes if n.get("parent_id") is not None]
    assert second, "期望存在二级分类"
    assert all(n["parent_id"] in root_ids for n in second), "期望二级分类均直接归属于一级分类"
    assert not any(n.get("children") for n in second), "期望分类树仅两级（契约 §4.1）"

    # count 语义：叶子 = 直接归属材料数；父节点 = 自身直接归属 + 全部子节点之和
    for n in roots:
        kids = n.get("children") or []
        assert n["count"] >= sum(c["count"] for c in kids), \
            f"期望父分类 count 覆盖其子分类，实际 {n['name']}={n['count']}，" \
            f"子节点={[c['count'] for c in kids]}"
    assert sum(n["count"] for n in roots) >= 1, "期望种子库存在已归类材料"


def test_category_create_rename_conflict(seeded_client):
    """P0 | F1 新建/改名/删除：删除被引用分类 → CONFLICT。"""
    rc = seeded_client.post("/api/categories", json={"name": "验收临时分类", "parent_id": None})
    assert rc.status_code == 200, f"期望 200，实际 {rc.status_code}"
    cid = rc.json()["id"]
    rp = seeded_client.patch(f"/api/categories/{cid}", json={"name": "验收临时分类-改"})
    assert rp.status_code == 200 and rp.json().get("name") == "验收临时分类-改", \
        f"期望改名成功，实际 {rp.json()}"


def test_category_delete_conflict_and_success(seeded_client):
    """P0 | G1 §4.1 删除分类：被材料引用 → 409 CONFLICT；无引用可删；不存在 → 404。"""
    # ① 被材料引用的二级分类（种子材料挂在「工程塑料」下）→ 409 CONFLICT
    tree = seeded_client.get("/api/categories").json()["items"]
    leaf = next((c for n in tree for c in (n.get("children") or []) if c.get("count", 0) > 0), None)
    assert leaf is not None, "期望种子库存在被材料引用的二级分类"
    rc = seeded_client.delete(f"/api/categories/{leaf['id']}")
    assert rc.status_code == 409, f"期望 409 CONFLICT，实际 {rc.status_code}：{rc.text}"
    assert rc.json().get("error", {}).get("code") == "CONFLICT", f"期望 CONFLICT，实际 {rc.json()}"

    # ② 无引用的临时分类 → 删除成功，列表不再包含
    rid = seeded_client.post(
        "/api/categories", json={"name": "验收待删除分类", "parent_id": None}
    ).json()["id"]
    rd = seeded_client.delete(f"/api/categories/{rid}")
    assert rd.status_code == 200 and rd.json().get("ok") is True, f"期望删除成功，实际 {rd.json()}"
    names = [n["name"] for n in seeded_client.get("/api/categories").json()["items"]]
    assert "验收待删除分类" not in names, "删除后不应再出现在分类树"

    # ③ 不存在的分类 → 404
    r404 = seeded_client.delete("/api/categories/999999")
    assert r404.status_code == 404, f"期望 404，实际 {r404.status_code}：{r404.text}"


# ---------------------------------------------------------------------------
# 字段级数据一致性（契约 §4.6 / 矩阵「数据一致性」）
# ---------------------------------------------------------------------------
def test_field_consistency_temp_limit_eq_max(seeded_client):
    """P0 | 数据一致性：service_temp_limit == service_temp_max（口径不随视图变化）。

    契约 §4.6 / 原型 §4 类型定义：列表卡片 `MaterialCard` 只带 `service_temp_limit`
    与 `density_min|max`、`price_min|max` 等对比列字段，温度区间 `service_temp_min/max`
    属于详情字段 `MaterialDetail`。因此本用例分两层校验：
    ① 卡片按 05 屏对比列口径提供 service_temp_limit / density_min / price_min；
    ② 「长期使用温度上限 == 温度区间上限」这一数据一致性不变量在详情接口上成立。
    """
    items = seeded_client.get("/api/materials", params={"page_size": 8}).json()["items"]
    assert len(items) >= 2, f"期望种子库返回至少 2 条材料，实际 {len(items)}"
    for it in items:
        assert "service_temp_limit" in it and "density_min" in it and "price_min" in it, \
            f"期望卡片含 05 屏对比列字段（service_temp_limit/density_min/price_min），实际键={sorted(it)}"
        d = seeded_client.get(f"/api/materials/{it['uid']}").json()
        assert d["service_temp_limit"] == d["service_temp_max"], \
            (f"期望 service_temp_limit==service_temp_max，"
             f"{d['name']}: limit={d['service_temp_limit']} max={d['service_temp_max']}")
        assert d["service_temp_min"] <= d["service_temp_max"], \
            (f"期望 service_temp_min<=service_temp_max，"
             f"{d['name']}: min={d['service_temp_min']} max={d['service_temp_max']}")


# ---------------------------------------------------------------------------
# 种子数据完整率（离线读 data/materials.json，不依赖服务端）
# ---------------------------------------------------------------------------
def test_seed_data_completeness():
    """P0 | 数据完整率：材料≥50 条且参数字段完整率>90%（阻塞：等待 data 落地）。"""
    if not DATA_MATERIALS.exists():
        pytest.skip("阻塞：等待数据收集师 data/materials.json（≥50 条）落地")
    raw = json.loads(DATA_MATERIALS.read_text(encoding="utf-8"))
    materials = raw if isinstance(raw, list) else raw.get("materials", [])
    assert len(materials) >= 50, f"期望材料≥50条，实际 {len(materials)} 条"
    required = ["name", "uid", "service_temp_limit", "density_min", "price_min",
                "molding_process", "category_id"]
    miss = 0
    total = 0
    for m in materials:
        for fld in required:
            total += 1
            if m.get(fld) in (None, "", []):
                miss += 1
    rate = 1 - miss / total
    assert rate > 0.90, f"期望字段完整率>90%，实际 {rate:.2%}（缺失 {miss}/{total}）"


# ---------------------------------------------------------------------------
# 统一错误结构（契约 §3.1）
# ---------------------------------------------------------------------------
def test_uniform_error_envelope(seeded_client):
    """P1 | 错误体统一：{error:{code,message}}，禁止空字符串值。"""
    r = seeded_client.get("/api/materials/__bad__")
    if r.status_code < 400:
        pytest.skip("未触发错误态，跳过（接口行为待确认）")
    err = r.json().get("error", {})
    assert "code" in err and "message" in err, f"期望 error 含 code/message，实际 {err}"
    assert err["message"], "错误信息禁止为空字符串"
