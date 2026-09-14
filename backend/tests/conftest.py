# -*- coding: utf-8 -*-
"""
MatSelect 验收测试基座（conftest）

设计目标（来自 docs/plan/02-接口契约与工程约定.md §2 / 验收任务书）：
1. 不污染生产库 data/matselect.db —— 通过环境变量 MATSELECT_DB 指向 session 级
   临时数据库文件，再调用 init_db() 建表。
2. 提供两个 fixture：
   - client        : 已建表的空库 TestClient（仅供不强依赖种子数据的用例）
   - seeded_client : 写入 ≥5 条「覆盖高/低温、不同工艺」的受控测试材料，
                     用于推荐算法、回评、对比等需要数据的用例。
3. 并发开发现实：backend/app/** 可能尚未落地。本基座在 import 失败时不会让
   整个 session 崩溃，而是让依赖它的用例以「阻塞：等待 XX 模块」干净 skip，
   并如实记录。绝不为了变绿而放宽断言或删用例。

注意：本文件只属于验收专家（backend/tests/**），禁止修改 backend/app/** 等他人文件。
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# ---- 路径注入：让 `import app.*` 可在 pytest 从 backend/ 启动时解析 ----
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---- 探测后端是否落地（架构师/后端专家负责 app/**）----
BACKEND_AVAILABLE = False
BACKEND_IMPORT_ERROR = None
APP = None
INIT_DB = None
try:
    # 必须在 import app 之前设置 MATSELECT_DB，避免 connection 模块在导入期
    # 缓存了默认路径 data/matselect.db。这里仅做探测性 import，真正的 DB 路径
    # 在每个 fixture 内再设置一次，确保隔离。
    from app.main import app as _APP                       # noqa: E402
    from app.db.init_db import init_db as _INIT_DB         # noqa: E402
    APP = _APP
    INIT_DB = _INIT_DB
    BACKEND_AVAILABLE = True
except Exception as _e:  # noqa: BLE001
    BACKEND_AVAILABLE = False
    BACKEND_IMPORT_ERROR = repr(_e)


# ---------------------------------------------------------------------------
# 测试态隔离：不加载真实种子数据
#
# 背景：应用 lifespan 会调用 init_db() + seed_if_empty()，后者从
# data/{categories,materials,term_alias}.json 导入 17 分类 / 50 材料 / 77 术语。
# 而本测试套件自带一套**受控种子**（SEED_CATEGORIES / SEED_MATERIALS，8 条，
# 覆盖高低温与不同工艺），用例的计数、完整率、放宽降级等断言都基于这套受控数据。
# 若真实种子同时入库，断言会因数据量不符而失真（例如「材料总数 == 8」变成 58）。
#
# 因此在本测试进程内把 seed_if_empty 置为空操作，保证初始库为空、
# 由 _seed_via_api() 通过 REST 黑盒写入受控数据。这是测试隔离，不是放宽断言。
#
# 备注：init_db._run_schema 曾因「按 ";" 朴素切分导致触发器被截断」需要打补丁；
# 该缺陷已由技术负责人修复（改为先探测 trigram 再整体 executescript），
# 此处不再打补丁，测试直接走真实代码路径。
# ---------------------------------------------------------------------------
if BACKEND_AVAILABLE:
    import app.db.init_db as _init_db_mod

    def _noop_seed_if_empty():
        """测试自带受控种子，隔离 data/*.json 的真实种子。"""
        return None

    _init_db_mod.seed_if_empty = _noop_seed_if_empty


# ===========================================================================

# 种子数据（受控、与 data/*.json 解耦，保证用例可重复）
# 字段名严格对齐契约 §4.5（= DDL 列名 = 前端 TS 字段名）。
# 区间字段为 xxx_min / xxx_max；service_temp_limit 单独抽列（硬约束口径）。
# ===========================================================================
SEED_CATEGORIES = [
    {"name": "热塑性塑料", "parent_id": None},
    {"name": "工程塑料", "parent_id": 1},
    {"name": "热固性塑料", "parent_id": None},
    {"name": "弹性体", "parent_id": None},
]

# 8 条：覆盖高温(≥200)/中温/低温(<100)、工艺注塑/挤出/模压、含反馈目标材料
SEED_MATERIALS = [
    {
        "name": "PPS+GF40（聚苯硫醚 40%玻纤）",
        "short_name": "PPS+GF40",
        "category_id": 2,
        "grade_type": "特种工程塑料",
        "aliases": ["PPS-GF40", "聚苯硫醚玻纤"],
        "description": "高温电气连接器壳体用料",
        "density_min": 1.66, "density_max": 1.68,
        "tensile_strength_min": 190, "tensile_strength_max": 210,
        "elastic_modulus_min": 13.0, "elastic_modulus_max": 15.0,
        "elongation_min": 1.5, "elongation_max": 2.5,
        "notch_impact_min": 8, "notch_impact_max": 12,
        "hdt_min": 260, "hdt_max": 270,
        "service_temp_min": -40, "service_temp_max": 220,
        "service_temp_limit": 220,
        "features": ["耐高温", "阻燃", "高刚性"],
        "cautions": [{"type": "脆性", "content": "缺口敏感，需避免尖角"}],
        "applications": ["连接器", "保险丝座", "传感器支架"],
        "price_min": 60, "price_max": 75,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["注塑"],
        "certifications": {"ul94": "V-0@1.5mm", "rohs": True, "reach": True},
        "limitations": ["低温冲击一般"],
        "source": "供应商手册A 2025版",
        "source_date": "2025-09-01",
        "value_type": "typical",
    },
    {
        "name": "PA66+GF30（30%玻纤增强尼龙66）",
        "short_name": "PA66+GF30",
        "category_id": 2,
        "grade_type": "工程塑料",
        "aliases": ["PA66-GF30", "尼龙66玻纤"],
        "description": "保险丝座/连接器常用电气件材料",
        "density_min": 1.34, "density_max": 1.37,
        "tensile_strength_min": 170, "tensile_strength_max": 190,
        "elastic_modulus_min": 9.0, "elastic_modulus_max": 11.0,
        "elongation_min": 3.0, "elongation_max": 5.0,
        "notch_impact_min": 10, "notch_impact_max": 14,
        "hdt_min": 245, "hdt_max": 255,
        "service_temp_min": -40, "service_temp_max": 150,
        "service_temp_limit": 150,
        "features": ["高强度", "抗蠕变", "阻燃可选"],
        "cautions": [{"type": "吸湿", "content": "成型前需充分干燥"}],
        "applications": ["保险丝座", "连接器外壳", "ECU壳体"],
        "price_min": 25, "price_max": 32,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["注塑"],
        "certifications": {"ul94": "V-0@1.6mm", "rohs": True, "reach": True},
        "limitations": ["各向异性", "外观需处理浮纤"],
        "source": "供应商手册B 2025版",
        "source_date": "2025-08-20",
        "value_type": "typical",
    },
    {
        "name": "PBT+GF30（30%玻纤增强PBT）",
        "short_name": "PBT+GF30",
        "category_id": 2,
        "grade_type": "工程塑料",
        "aliases": ["PBT-GF30"],
        "description": "电气外壳，性价比之选",
        "density_min": 1.50, "density_max": 1.53,
        "tensile_strength_min": 110, "tensile_strength_max": 130,
        "elastic_modulus_min": 8.0, "elastic_modulus_max": 9.5,
        "elongation_min": 3.0, "elongation_max": 4.5,
        "notch_impact_min": 8, "notch_impact_max": 11,
        "hdt_min": 205, "hdt_max": 215,
        "service_temp_min": -40, "service_temp_max": 140,
        "service_temp_limit": 140,
        "features": ["尺寸稳定", "阻燃", "低成本"],
        "cautions": [{"type": "耐温", "content": "长期耐温低于PA66"}],
        "applications": ["连接器", "继电器壳"],
        "price_min": 22, "price_max": 28,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["注塑"],
        "certifications": {"ul94": "V-0@1.6mm", "rohs": True, "reach": True},
        "limitations": ["耐温有限"],
        "source": "供应商手册B 2025版",
        "source_date": "2025-08-22",
        "value_type": "typical",
    },
    {
        "name": "PP（均聚聚丙烯 PP-H）",
        "short_name": "PP-H",
        "category_id": 2,
        "grade_type": "通用塑料",
        "aliases": ["PP-H", "聚丙烯", "均聚PP"],
        "description": "内饰卡扣等低成本件",
        "density_min": 0.90, "density_max": 0.91,
        "tensile_strength_min": 30, "tensile_strength_max": 40,
        "elastic_modulus_min": 1.2, "elastic_modulus_max": 1.6,
        "elongation_min": 50, "elongation_max": 200,
        "notch_impact_min": 3, "notch_impact_max": 5,
        "hdt_min": 90, "hdt_max": 100,
        "service_temp_min": -20, "service_temp_max": 100,
        "service_temp_limit": 100,
        "features": ["密度小", "成本低", "耐化学"],
        "cautions": [{"type": "低温脆", "content": "低温脆、抗UV差"}],
        "applications": ["内饰卡扣", "暖风出风口"],
        "price_min": 8, "price_max": 10,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["注塑"],
        "certifications": {"ul94": "HB", "rohs": True, "reach": True},
        "limitations": ["耐温低"],
        "source": "供应商手册A 2025版",
        "source_date": "2025-09-02",
        "value_type": "typical",
    },
    {
        "name": "EPDM（三元乙丙橡胶）",
        "short_name": "EPDM",
        "category_id": 4,
        "grade_type": "弹性体",
        "aliases": ["三元乙丙", "EPDM橡胶"],
        "description": "密封条，耐候低温",
        "density_min": 0.86, "density_max": 0.90,
        "tensile_strength_min": 8, "tensile_strength_max": 15,
        "elastic_modulus_min": 0.005, "elastic_modulus_max": 0.02,
        "elongation_min": 200, "elongation_max": 400,
        "notch_impact_min": 0, "notch_impact_max": 0,
        "hdt_min": 0, "hdt_max": 0,
        "service_temp_min": -50, "service_temp_max": 130,
        "service_temp_limit": 130,
        "features": ["耐候", "耐低温", "密封"],
        "cautions": [{"type": "强度低", "content": "不能作为承力件"}],
        "applications": ["密封条", "防水圈"],
        "price_min": 18, "price_max": 26,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["挤出", "模压"],
        "certifications": {"rohs": True, "reach": True},
        "limitations": ["不耐油"],
        "source": "供应商手册C 2025版",
        "source_date": "2025-09-03",
        "value_type": "typical",
    },
    {
        "name": "PF（酚醛模塑料）",
        "short_name": "PF",
        "category_id": 3,
        "grade_type": "热固性塑料",
        "aliases": ["电木", "酚醛"],
        "description": "高温绝缘件，电器骨架",
        "density_min": 1.35, "density_max": 1.45,
        "tensile_strength_min": 40, "tensile_strength_max": 60,
        "elastic_modulus_min": 8.0, "elastic_modulus_max": 12.0,
        "elongation_min": 0.5, "elongation_max": 1.5,
        "notch_impact_min": 2, "notch_impact_max": 5,
        "hdt_min": 150, "hdt_max": 180,
        "service_temp_min": -40, "service_temp_max": 180,
        "service_temp_limit": 180,
        "features": ["耐高温", "绝缘", "尺寸稳定"],
        "cautions": [{"type": "脆性", "content": "质脆"}],
        "applications": ["电器骨架", "端子板"],
        "price_min": 12, "price_max": 18,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["模压"],
        "certifications": {"ul94": "V-1", "rohs": True, "reach": True},
        "limitations": ["脆性"],
        "source": "供应商手册C 2025版",
        "source_date": "2025-09-04",
        "value_type": "typical",
    },
    {
        "name": "PA6+GF30（30%玻纤增强尼龙6）",
        "short_name": "PA6+GF30",
        "category_id": 2,
        "grade_type": "工程塑料",
        "aliases": ["PA6-GF30"],
        "description": "承力支架，耐温略低于PA66",
        "density_min": 1.33, "density_max": 1.36,
        "tensile_strength_min": 160, "tensile_strength_max": 180,
        "elastic_modulus_min": 8.5, "elastic_modulus_max": 10.5,
        "elongation_min": 3.0, "elongation_max": 5.0,
        "notch_impact_min": 10, "notch_impact_max": 14,
        "hdt_min": 210, "hdt_max": 220,
        "service_temp_min": -40, "service_temp_max": 135,
        "service_temp_limit": 135,
        "features": ["高强度", "韧性好"],
        "cautions": [{"type": "吸湿", "content": "需干燥"}],
        "applications": ["支架", "齿轮"],
        "price_min": 23, "price_max": 29,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["注塑"],
        "certifications": {"ul94": "V-0@1.6mm", "rohs": True, "reach": True},
        "limitations": ["耐温有限"],
        "source": "供应商手册B 2025版",
        "source_date": "2025-08-25",
        "value_type": "typical",
    },
    {
        "name": "LCP（液晶聚合物）",
        "short_name": "LCP",
        "category_id": 2,
        "grade_type": "特种工程塑料",
        "aliases": ["液晶聚合物"],
        "description": "超薄高频连接器，高温低翘曲",
        "density_min": 1.60, "density_max": 1.70,
        "tensile_strength_min": 150, "tensile_strength_max": 180,
        "elastic_modulus_min": 12.0, "elastic_modulus_max": 16.0,
        "elongation_min": 2.0, "elongation_max": 4.0,
        "notch_impact_min": 5, "notch_impact_max": 9,
        "hdt_min": 270, "hdt_max": 290,
        "service_temp_min": -40, "service_temp_max": 240,
        "service_temp_limit": 240,
        "features": ["耐高温", "低翘曲", "高频优"],
        "cautions": [{"type": "各向异性", "content": "接缝强度低"}],
        "applications": ["高频连接器", "微型骨架"],
        "price_min": 90, "price_max": 120,
        "price_unit": "元/kg",
        "price_note": "随行情波动",
        "molding_process": ["注塑"],
        "certifications": {"ul94": "V-0@0.4mm", "rohs": True, "reach": True},
        "limitations": ["成本高"],
        "source": "供应商手册A 2025版",
        "source_date": "2025-09-05",
        "value_type": "typical",
    },
]


def _seed_via_api(client):
    """通过 REST API 写入受控种子数据（黑盒，不依赖 data/*.json）。"""
    # 1) 分类
    cat_ids = {}
    for cat in SEED_CATEGORIES:
        r = client.post("/api/categories", json=cat)
        if r.status_code == 200:
            cat_ids[cat["name"]] = r.json().get("id")
    # 若分类已存在（重入），尝试 GET 建立 id 映射
    if len(cat_ids) < len(SEED_CATEGORIES):
        r = client.get("/api/categories")
        if r.status_code == 200:
            for node in r.json().get("items", []):
                cat_ids.setdefault(node["name"], node["id"])
                for child in node.get("children", []) if "children" in node else []:
                    cat_ids.setdefault(child["name"], child["id"])
    # 2) 材料（category_id 用映射后的真实 id）
    created = []
    for m in SEED_MATERIALS:
        body = dict(m)
        if m["category_id"] is not None:
            # 用名称反查（SEED_CATEGORIES 顺序 1..N）
            cat_name = [c["name"] for c in SEED_CATEGORIES if c.get("parent_id") is None
                        or True][m["category_id"] - 1] if m["category_id"] <= len(SEED_CATEGORIES) else None
            body["category_id"] = cat_ids.get(cat_name, m["category_id"])
        r = client.post("/api/materials", json=body)
        if r.status_code == 200:
            created.append(r.json())
    return created


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(scope="session")
def tmp_db_path():
    """session 级临时库文件，绝不指向 data/matselect.db。"""
    fd, path = tempfile.mkstemp(prefix="matselect_test_", suffix=".db")
    os.close(fd)
    os.remove(path)  # 让 init_db() 自己建表
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture(scope="session")
def backend_app():
    """后端 app 是否可用。不可用 → 依赖它的用例干净 skip（阻塞项）。"""
    if not BACKEND_AVAILABLE:
        pytest.skip(
            "阻塞：等待后端模块落地（架构师 backend/app/main.py、backend/app/db/init_db.py、"
            "后端专家 backend/app/api|services|schemas）。import 失败原因: "
            + str(BACKEND_IMPORT_ERROR)
        )
    return APP


@pytest.fixture()
def client(backend_app, tmp_db_path):
    """已建表的 TestClient；DB 来自临时文件，不污染生产库。"""
    os.environ["MATSELECT_DB"] = tmp_db_path
    if INIT_DB is not None:
        INIT_DB()
    from fastapi.testclient import TestClient

    with TestClient(backend_app) as c:
        yield c
    # 还原环境，避免影响其它进程
    os.environ.pop("MATSELECT_DB", None)


@pytest.fixture(scope="session")
def seeded_client(backend_app, tmp_db_path):
    """写入受控种子材料的 TestClient（session 级，仅建一次）。"""
    os.environ["MATSELECT_DB"] = tmp_db_path
    if INIT_DB is not None:
        INIT_DB()
    from fastapi.testclient import TestClient

    with TestClient(backend_app) as c:
        _seed_via_api(c)
        yield c
    os.environ.pop("MATSELECT_DB", None)
