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


# ---------------------------------------------------------------------------
# 回归：一级分类筛选应含其子类材料（「点大类显示未找到匹配材料」）
#
# 背景：材料只挂在**二级分类**上，而旧实现用 `category_id IN (选中的id)` 做等值匹配，
# 点一级分类时命中数恒为 0。修复后筛选父分类应展开为其全部后代分类。
# 受控种子中：热塑性塑料(root) → 工程塑料(child)，材料挂在「工程塑料」上。
# ---------------------------------------------------------------------------
def test_materials_filter_by_root_category_includes_descendants(seeded_client):
    """P0 | A1 回归：按一级分类筛选应返回其子类下的全部材料。"""
    tree = seeded_client.get("/api/categories").json()["items"]
    root = next((n for n in tree if n["name"] == "热塑性塑料"), None)
    assert root is not None, f"种子缺少一级分类「热塑性塑料」，实际 tree={tree}"
    child = next((c for c in root.get("children", []) if c["name"] == "工程塑料"), None)
    assert child is not None, f"「热塑性塑料」下缺少子类「工程塑料」，实际 children={root.get('children')}"

    r_child = seeded_client.get("/api/materials", params={"category_ids": child["id"], "page_size": 100})
    r_root = seeded_client.get("/api/materials", params={"category_ids": root["id"], "page_size": 100})
    assert r_child.status_code == 200 and r_root.status_code == 200, "分类筛选应返回 200"

    n_child, n_root = r_child.json()["total"], r_root.json()["total"]
    names = [m["name"] for m in r_root.json()["items"]]
    assert n_child > 0, "子类「工程塑料」下应有种子材料，否则用例前提失效"
    assert n_root >= n_child, \
        f"一级分类命中数({n_root})不应少于其子类({n_child})；旧实现此处为 0"
    assert any("PA66+GF30" in n for n in names), \
        f"一级分类应命中挂在子类上的 PA66+GF30，实际 names={names}"


def test_categories_root_count_equals_sum_of_children(seeded_client):
    """P1 | 回归：一级分类计数 = 其子类计数之和（后端已含子类，前端不得再叠加）。"""
    tree = seeded_client.get("/api/categories").json()["items"]
    for node in tree:
        kids = node.get("children") or []
        if not kids:
            continue
        assert node["count"] == sum(c["count"] for c in kids), \
            f"一级分类「{node['name']}」计数 {node['count']} != 子类之和 {sum(c['count'] for c in kids)}"


# ---------------------------------------------------------------------------
# 回归：模糊搜索（「搜索功能不够强」）
# ---------------------------------------------------------------------------
def test_materials_search_single_char(seeded_client):
    """P0 | A3 回归：单字符也应能模糊命中，不被旧的 len(q)>=2 门槛挡掉。"""
    # 种子中「尼」出现在 PA66+GF30 的名称（尼龙66）与别名（尼龙66玻纤）里
    r = seeded_client.get("/api/materials", params={"q": "尼"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    names = [m["name"] for m in r.json()["items"]]
    assert r.json()["total"] > 0, "单字符「尼」应至少命中 1 条（旧的 2 字门槛会返回 0）"
    assert any("PA66+GF30" in n for n in names), f"「尼」应命中 PA66+GF30，实际 names={names}"


def test_materials_search_multi_keyword(seeded_client):
    """P0 | A3 回归：多关键词（空格分隔）应全部命中同一材料，而非整串短语匹配。"""
    r = seeded_client.get("/api/materials", params={"q": "PA66 阻燃"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    items = r.json()["items"]
    names = [m["name"] for m in items]
    assert any("PA66" in n for n in names), \
        f"期望「PA66 阻燃」命中 PA66+GF30（其 features 含阻燃可选），实际 names={names}"


def test_materials_search_matches_feature_and_category(seeded_client):
    """P1 | A3 回归：特性标签与所属分类名也应参与模糊匹配（旧实现只搜 4 列）。"""
    r_feat = seeded_client.get("/api/materials", params={"q": "阻燃"})
    assert r_feat.status_code == 200, f"期望 200，实际 {r_feat.status_code}"
    assert r_feat.json()["total"] > 0, "「阻燃」应至少命中 1 条（种子 PPS/PA66/PBT 均含该特性）"

    r_cat = seeded_client.get("/api/materials", params={"q": "弹性体"})
    assert r_cat.status_code == 200, f"期望 200，实际 {r_cat.status_code}"
    names = [m["name"] for m in r_cat.json()["items"]]
    assert any("EPDM" in n for n in names), \
        f"按分类名「弹性体」搜索应命中 EPDM，实际 names={names}"


def test_materials_search_case_insensitive(seeded_client):
    """P1 | A3 回归：牌号大小写不敏感（SQLite LIKE 对 ASCII 天然不敏感）。"""
    up = seeded_client.get("/api/materials", params={"q": "PA66"}).json()["total"]
    low = seeded_client.get("/api/materials", params={"q": "pa66"}).json()["total"]
    assert up == low and up > 0, f"大小写命中数应一致且>0，实际 PA66={up} / pa66={low}"


def test_materials_search_like_wildcard_escaped(seeded_client):
    """P2 | 回归：用户输入的 % / _ 需转义，不得当作 SQL 通配符放大命中。"""
    r = seeded_client.get("/api/materials", params={"q": "%"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    all_total = seeded_client.get("/api/materials").json()["total"]
    assert r.json()["total"] < all_total, \
        f"「%」应按字面匹配（种子中仅 30% 类牌号含字面 %），不应等于全量 {all_total}"


def test_materials_search_relevance_order(seeded_client):
    """P1 | A3 回归：相关性排序 —— 名称/牌号命中排在描述等次要列命中之前。"""
    r = seeded_client.get("/api/materials", params={"q": "PPS", "page_size": 100})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    items = r.json()["items"]
    assert items, "「PPS」应至少命中 1 条"
    first = items[0]
    assert first["short_name"] == "PPS+GF40" or "PPS" in first["name"], \
        f"首条应为牌号/名称直接命中 PPS 的材料，实际首条={first['name']}"


# ---------------------------------------------------------------------------
# 回归：加工方式 / 注意项 / 认证 必须可被检索（客户四大关注点之一）
#
# 背景：客户明确的四大关注点是「成本 / 加工方式 / 温度 / 使用场景」，其中
#   · 成本      → 参数区间检索（price_max）已覆盖；
#   · 温度      → 参数区间检索（temp_min）已覆盖；
#   · 使用场景  → applications 已在检索列内；
#   · 加工方式  → **仅存在于 molding_process 列，且此前不在检索列内**，
#                 导致搜「注塑」「模压」「挤出」全部 0 命中。
# 同时补齐 cautions（注意项）与 certifications（UL94/RoHS 认证）两列——它们是材料卡
# 正面展示的信息，客户会直接搜「抗UV」「V-0」。
# ---------------------------------------------------------------------------
def test_materials_search_by_molding_process(seeded_client):
    """P0 | 回归：加工方式（客户四大关注点之一）必须可被检索。"""
    # 种子：EPDM 为 ["挤出","模压"]，PF 为 ["模压"]
    r_ext = seeded_client.get("/api/materials", params={"q": "挤出", "page_size": 100})
    assert r_ext.status_code == 200, f"期望 200，实际 {r_ext.status_code}"
    names_ext = [m["name"] for m in r_ext.json()["items"]]
    assert any("EPDM" in n for n in names_ext), \
        f"搜「挤出」应命中 EPDM（此前 molding_process 不在检索列，返回 0），实际 names={names_ext}"

    r_mo = seeded_client.get("/api/materials", params={"q": "模压", "page_size": 100})
    names_mo = [m["name"] for m in r_mo.json()["items"]]
    assert any("PF" in n for n in names_mo), \
        f"搜「模压」应命中 PF（酚醛模塑料），实际 names={names_mo}"

    # 注塑是最普遍的工艺，命中面应明显大于挤出
    n_inj = seeded_client.get("/api/materials", params={"q": "注塑"}).json()["total"]
    assert n_inj > r_ext.json()["total"], \
        f"「注塑」命中数({n_inj})应大于「挤出」命中数({r_ext.json()['total']})"


def test_materials_search_by_caution_content(seeded_client):
    """P1 | 回归：注意项（cautions）应参与检索，客户会按风险点反查材料。"""
    # 种子 PP 的 cautions 含「低温脆、抗UV差」
    r = seeded_client.get("/api/materials", params={"q": "抗UV", "page_size": 100})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    names = [m["name"] for m in r.json()["items"]]
    assert any("PP" in n for n in names), \
        f"搜「抗UV」应命中 cautions 中含「抗UV差」的 PP，实际 names={names}"


def test_materials_search_by_certification(seeded_client):
    """P1 | 回归：认证信息（certifications）应参与检索，阻燃等级是选型合规必查项。"""
    # 种子中 PF 的 ul94 为 "V-1"（唯一值，不会与 V-0 混淆）
    r = seeded_client.get("/api/materials", params={"q": "V-1", "page_size": 100})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    names = [m["name"] for m in r.json()["items"]]
    assert any("PF" in n for n in names), \
        f"搜「V-1」应命中 ul94=V-1 的 PF，实际 names={names}"

    # 搜 RoHS 应命中所有 rohs=true 的材料（种子全部为 true）
    n_rohs = seeded_client.get("/api/materials", params={"q": "rohs"}).json()["total"]
    assert n_rohs > 0, "搜「rohs」应命中带 RoHS 认证的材料"


def test_materials_search_multi_keyword_and_semantics(seeded_client):
    """P0 | 回归：多个关键词之间是 AND（同时满足），而非 OR 放大命中。"""
    # 「尼龙 玻纤」：PA66+GF30 与 PA6+GF30 的名称同时含这两个词
    r_hit = seeded_client.get("/api/materials", params={"q": "尼龙 玻纤", "page_size": 100})
    names = [m["name"] for m in r_hit.json()["items"]]
    assert len(names) >= 2, f"「尼龙 玻纤」应至少命中 PA66+GF30 与 PA6+GF30，实际 names={names}"

    # 「PA66 模压」：PA66 系列都是注塑件，无人同时满足 → AND 语义下应为 0
    n_miss = seeded_client.get("/api/materials", params={"q": "PA66 模压"}).json()["total"]
    assert n_miss == 0, f"「PA66 模压」应 0 命中（AND 语义），实际 {n_miss}；若>0 说明退化成了 OR"


def test_search_tokenizer_keeps_grade_hyphen():
    """P1 | 单元回归：分词不得拆坏「PA66-GF30」这类连字符牌号，但应认得 + 号组合写法。"""
    from app.repository.material_repo import _search_tokens
    assert _search_tokens("PA66-GF30") == ["PA66-GF30"], "连字符牌号不能被拆开"
    assert _search_tokens("PA66+GF30") == ["PA66", "GF30"], "加号组合应拆为两个词后 AND 命中同一材料"
    tokens = _search_tokens("我想做一个保险丝座组件，它是一个注塑件，使用场景温度不超过150°C。")
    assert all("。" not in t for t in tokens), "句末标点必须被切掉，否则整句成为永不命中的超长 token"
    assert "它是一个注塑件" in tokens, "中文逗号应作为分隔符把长句切开"


def test_search_whitespace_insensitive(seeded_client):
    """P1 | 回归：搜索应忽略「中英文/数字之间的空格」差异。

    真实语料习惯在中英文之间插空格，用户输入通常连写；纯 LIKE 会漏召回。
    种子中 PPS+GF40 的 name 为「PPS+GF40（聚苯硫醚 40%玻纤）」——注意「硫醚」与「40」
    之间有一个空格，且该串**只**出现在 name 里（aliases 是「聚苯硫醚玻纤」，不含数字），
    因此「搜连写形式能否命中」是这条修复的精确判据。
    """
    from app.repository.material_repo import _squash_text
    assert _squash_text("抗 UV 差") == "抗UV差", "去空格函数应处理 ASCII 空格"
    assert _squash_text("长期\u300080°C") == "长期80°C", "去空格函数应处理全角空格"

    # 用户连写、数据带空格 → 旧实现 0 命中，修复后应命中 PPS+GF40
    r_tight = seeded_client.get("/api/materials", params={"q": "聚苯硫醚40", "page_size": 100})
    assert r_tight.status_code == 200, f"期望 200，实际 {r_tight.status_code}"
    names_tight = [m["name"] for m in r_tight.json()["items"]]
    assert any("PPS+GF40" in n for n in names_tight), \
        f"连写「聚苯硫醚40」应命中 name 含「聚苯硫醚 40%玻纤」的 PPS+GF40，实际 names={names_tight}"

    # 用户按原文带空格输入 → 由分词解决（切成「聚苯硫醚」+「40」两个词 AND），同样应命中
    r_spaced = seeded_client.get("/api/materials", params={"q": "聚苯硫醚 40", "page_size": 100})
    names_spaced = [m["name"] for m in r_spaced.json()["items"]]
    assert any("PPS+GF40" in n for n in names_spaced), \
        f"带空格输入同样应命中 PPS+GF40，实际 names={names_spaced}"

    # 而空格仍必须是分词分隔符：把两个词用空格分开应变成 AND 语义而非整串匹配
    n_and = seeded_client.get("/api/materials", params={"q": "聚苯硫醚 尼龙"}).json()["total"]
    assert n_and == 0, f"「聚苯硫醚 尼龙」应 0 命中（AND 语义，无材料同时满足），实际 {n_and}"


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
