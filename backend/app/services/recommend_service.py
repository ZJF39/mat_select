# -*- coding: utf-8 -*-
"""智能推荐引擎（契约 §5 / PRD §5.1–§5.4）。

四段式：① 约束抽取 → ② 硬约束过滤（安全底线）→ ③ 加权排序 → ④ 模板化解释。

铁律：
- 第 ② 段**绝不返回不满足硬约束的材料**（`service_temp_limit >= 需求温度`、工艺匹配、未归档）。
- 第 ④ 段一律「模板 + 槽位填充」，**reason 中出现的每个数值都必须来自库中字段**，禁止编造。
- 反馈降权为**软降权**：材料仍在列表内，只是排序靠后，并标注「因历史反馈降分」。
"""
from __future__ import annotations

import re
from typing import List, Optional

from app.repository import material_repo
from app.repository.base import query_all
from app.repository.feedback_repo import hits_for_materials
from app.repository.settings_repo import (
    get_penalty,
    get_penalty_dim_weights,
    get_weights_fraction,
)
from app.services.embedding import similarity

# ---------------------------------------------------------------- 领域词典
# 零件类型 → 归类（承力件 / 电气件 / 外观件），用于力学维度加权
PART_TYPE_DICT = {
    "保险丝座": "电气件", "熔断器底座": "电气件", "保险丝盒": "电气件", "fuse holder": "电气件",
    "连接器": "电气件", "接插件": "电气件", "端子台": "电气件", "connector": "电气件",
    "继电器底座": "电气件", "继电器座": "电气件", "插座": "电气件",
    "ECU壳体": "结构件", "控制器外壳": "结构件", "电控单元壳体": "结构件", "外壳": "结构件",
    "传感器支架": "结构件", "传感器座": "结构件", "支架": "结构件", "底板": "结构件",
    "卡扣": "外观件", "卡子": "外观件", "clip": "外观件",
    "出风口": "外观件", "风道": "外观件", "装饰件": "外观件", "面板": "外观件",
}

PROCESS_DICT = ["注塑", "注射成型", "射出成型", "挤出", "挤塑", "吹塑", "压铸", "冲压",
                "机加工", "模压", "双色注塑", "热压", "真空成型"]

# 额外约束关键词 → 归一标签
EXTRA_KEYWORDS = {
    "阻燃": ["阻燃", "防火", "ul94", "v-0", "v0"],
    "耐油": ["耐油", "抗油"],
    "绝缘": ["绝缘", "电气绝缘"],
    "耐候": ["耐候", "抗uv", "抗紫外", "户外"],
    "低成本": ["便宜", "成本敏感", "预算低", "降本", "低成本", "省钱"],
    "高强度": ["高强度", "承力", "受力", "结构强度"],
    "透明": ["透明", "透光"],
}

_TEMP_RE = re.compile(r"(\d{2,3})\s*(?:°\s*c|℃|度|摄氏度)", re.IGNORECASE)

# 语义维度「不可评价」时的中性基线（契约 §5.3 只定义语义为 cosine(user_text, 材料文本)；
# 当调用方仅传结构化约束、没有场景文本时（POST /api/recommend/run 的常态），
# cosine 恒为 0 会把达标材料的综合分压到 60 分门槛以下 → 推荐主流程整体空结果。
# 与成本维度「用户未提成本 → 中性基线」同一原则，此处同样给中性基线。）
SEMANTIC_NEUTRAL = 0.5

# 力学维度：按零件类型给特性关键词加权
_MECHANICS_BY_PART = {
    "电气件": (("阻燃", 0.4), ("绝缘", 0.3), ("耐温", 0.15), ("强度", 0.15)),
    "结构件": (("强度", 0.45), ("刚性", 0.2), ("抗蠕变", 0.2), ("耐温", 0.15)),
    "外观件": (("易成型", 0.35), ("表面", 0.25), ("密度", 0.2), ("成本", 0.2)),
    None: (("强度", 0.4), ("耐温", 0.3), ("易成型", 0.3)),
}


# ---------------------------------------------------------------- ① 约束抽取


def _synonym_index() -> dict:
    """从 term_alias 表构建 {同义词: 标准术语} 映射（PRD §5.4）。"""
    idx = {}
    try:
        rows = query_all("SELECT standard, synonym, type FROM term_alias")
    except Exception:  # noqa: BLE001 - 词典缺失不应阻断推荐
        return idx
    for r in rows:
        syn = (r["synonym"] or "").strip()
        std = (r["standard"] or "").strip()
        if syn and std:
            idx[syn.lower()] = std
    return idx


def parse(text: str, task_id: Optional[int] = None) -> dict:
    """第 1 段：约束抽取。规则 + 词典 + 正则为主，不做开放式语义理解。

    返回 {constraints, confidence, degraded, raw_text}
    """
    raw = (text or "").strip()
    low = raw.lower()
    synonyms = _synonym_index()

    # 零件类型
    part_type = None
    for kw, kind in PART_TYPE_DICT.items():
        if kw.lower() in low:
            part_type = kind
            break
    if part_type is None:
        # 借助术语词典把同义表述映射后重试
        for syn, std in synonyms.items():
            if syn and syn in low and std in PART_TYPE_DICT:
                part_type = PART_TYPE_DICT[std]
                break

    # 工艺
    process = None
    for p in PROCESS_DICT:
        if p in raw:
            process = p
            break
    if process is None:
        for syn, std in synonyms.items():
            if syn and syn in low and std in PROCESS_DICT:
                process = std
                break

    # 温度上限
    temp_limit = None
    m = _TEMP_RE.search(raw)
    if m:
        try:
            temp_limit = float(m.group(1))
        except ValueError:
            temp_limit = None

    # 额外约束
    extra: List[str] = []
    for label, kws in EXTRA_KEYWORDS.items():
        if any(k.lower() in low for k in kws):
            extra.append(label)

    hits = sum(1 for v in (part_type, process, temp_limit) if v is not None)
    confidence = round(hits / 3.0, 2)
    degraded = hits == 0

    return {
        "constraints": {
            "part_type": part_type,
            "process": process,
            "temp_limit": temp_limit,
            "extra": extra,
        },
        "confidence": confidence,
        "degraded": degraded,
        "raw_text": raw,
    }


# ---------------------------------------------------------------- ② 硬约束过滤


def _hard_filter(constraints: dict, temp_override: Optional[float] = None):
    """纯 SQL 硬约束过滤。返回候选卡片列表（已含 category 信息）。"""
    temp = constraints.get("temp_limit")
    if temp_override is not None:
        temp = temp_override
    processes = None
    if constraints.get("process"):
        processes = constraints["process"]
    _, items = material_repo.list_materials(
        q=None,
        category_ids=None,
        processes=processes,
        temp_min=temp if temp is not None else None,
        price_max=None,
        flame=None,
        features=None,
        sort="service_temp_limit",
        order="desc",
        archived=0,
        page=1,
        page_size=500,
    )
    # 二次防线：即便 repository 条件有偏差，也绝不放行不满足硬约束的材料
    if temp is not None:
        items = [i for i in items if (i.get("service_temp_limit") or -1e9) >= float(temp)]
    if constraints.get("process"):
        p = constraints["process"]
        items = [i for i in items if any(p in str(x) for x in (i.get("molding_process") or []))]
    return items


# ---------------------------------------------------------------- ③ 加权排序


def _temp_score(limit: Optional[float], need: Optional[float]) -> float:
    """温度裕度：0~20% 裕度给满分；裕度过大线性扣分（避免过度设计）。

    契约 §5.3 明确「裕度 0~20% 得满分」：`service_temp_limit` 恰好等于需求温度
    属于硬约束达标（`>=`），裕度为 0 必须给满分；仅当低于需求（裕度为负，
    正常已被第 ② 段过滤）才给 0。
    """
    if need is None or limit is None:
        return 0.7
    margin = float(limit) - float(need)
    if margin < 0:
        return 0.0
    ratio = margin / max(float(need), 1.0)
    if ratio <= 0.2:
        return 1.0
    if ratio >= 1.0:
        return 0.4
    return 1.0 - 0.6 * (ratio - 0.2) / 0.8


def _semantic_score(user_text: str, material: dict) -> float:
    parts = [
        str(material.get("description") or ""),
        " ".join(material.get("features") or []),
        " ".join(material.get("applications") or []),
        str(material.get("name") or ""),
        " ".join(material.get("aliases") or []),
    ]
    return similarity(user_text, " ".join(p for p in parts if p))


def _cost_score(material: dict, cost_sensitive: bool) -> float:
    """成本匹配：未提成本时给中性基线；成本敏感时按参考价线性给分。"""
    price = material.get("price_max")
    if price is None:
        price = material.get("price_min")
    if price is None:
        return 0.5
    if not cost_sensitive:
        return 0.6
    if price <= 15:
        return 1.0
    if price >= 80:
        return 0.2
    return 1.0 - 0.8 * (float(price) - 15) / 65.0


def _mechanics_score(material: dict, part_type: Optional[str]) -> float:
    spec = _MECHANICS_BY_PART.get(part_type, _MECHANICS_BY_PART[None])
    text = " ".join(material.get("features") or []) + str(material.get("description") or "")
    total = sum(w for _, w in spec) or 1.0
    got = 0.0
    for kw, w in spec:
        if kw in text:
            got += w
    # 无任何命中时给基线，避免全 0 导致总分失真
    base = 0.4 if got == 0 else 0.0
    return min(1.0, base + got / total)


def _process_score(material: dict, process: Optional[str]) -> float:
    if not process:
        return 0.6
    procs = [str(x) for x in (material.get("molding_process") or [])]
    if any(process == p for p in procs):
        return 1.0
    if any(process in p or p in process for p in procs):
        return 0.7
    return 0.3


def _feedback_penalty(hits: dict, dim_weights: dict, threshold: int, max_penalty: float) -> float:
    """契约 §5.2：Σ_d min(hits_d/THRESHOLD,1) * DIM_WEIGHT[d] * PENALTY_MAX。

    **单条负面不降权**（hits < threshold 贡献 0）。
    """
    if not hits or threshold <= 0:
        return 0.0
    penalty = 0.0
    for dim, cnt in hits.items():
        if cnt < threshold:
            continue
        w = float(dim_weights.get(dim, 0.0))
        penalty += min(cnt / float(threshold), 1.0) * w * float(max_penalty)
    return round(min(penalty, float(max_penalty)), 2)


# ---------------------------------------------------------------- ④ 解释生成


def _fmt_range(lo, hi) -> str:
    if lo is None and hi is None:
        return "—"
    if lo is None:
        return f"≤ {hi}"
    if hi is None:
        return str(lo)
    return str(lo) if lo == hi else f"{lo}–{hi}"


def build_key_params(material: dict) -> List[str]:
    """关键参数：顺序固定 拉伸强度 → 长期耐温上限 → 参考价 → 密度 → 推荐工艺。"""
    ts = _fmt_range(material.get("tensile_strength_min"), material.get("tensile_strength_max"))
    limit = material.get("service_temp_limit")
    price = _fmt_range(material.get("price_min"), material.get("price_max"))
    unit = material.get("price_unit") or ""
    density = _fmt_range(material.get("density_min"), material.get("density_max"))
    procs = "、".join(material.get("molding_process") or []) or "—"
    return [
        f"拉伸强度：{ts} MPa",
        f"长期耐温上限：{limit if limit is not None else '—'} °C",
        f"参考价：{price}{(' ' + unit) if unit else ''}",
        f"密度：{density} g/cm³",
        f"推荐工艺：{procs}",
    ]


def build_reason(material: dict, constraints: dict, dims: dict, penalty: float) -> str:
    """模板 + 槽位填充。所有数值均取自 material，零编造。

    以「材料名：」开头：reason 会被短名单、对比导出与验收报告**脱离卡片标题**单独引用，
    带上库中真实材料名是契约 §5.4「零编造」的可追溯锚点。
    """
    segs: List[str] = []
    need = constraints.get("temp_limit")
    limit = material.get("service_temp_limit")
    if need is not None and limit is not None:
        segs.append(f"长期最高使用温度 {int(limit)} °C，满足场景温度上限 {int(need)} °C 的硬约束")
    if constraints.get("process"):
        procs = "、".join(material.get("molding_process") or [])
        segs.append(f"推荐成型工艺为 {procs}，与需求的「{constraints['process']}」匹配")
    feats = material.get("features") or []
    if feats:
        segs.append("主要特性 " + "、".join(str(x) for x in feats[:4]) + " 契合零件使用要求")
    parts = material.get("applications") or []
    if parts:
        segs.append("典型应用含 " + "、".join(str(x) for x in parts[:3]))
    if constraints.get("extra"):
        segs.append("已考虑额外约束：" + "、".join(constraints["extra"]))
    if dims.get("semantic", 0) >= 0.5:
        segs.append("与您的场景描述语义相似度较高")
    if penalty:
        segs.append(f"（因历史反馈降分 {abs(penalty):.1f}）")
    if not segs:
        segs.append("在硬约束过滤后的候选集中综合匹配度最高")
    name = str(material.get("name") or "").strip()
    body = "；".join(segs) + "。"
    return f"{name}：{body}" if name else body


def _build_alternatives(ranked: List[dict], idx: int, top: dict) -> List[dict]:
    """替代方案 = 第 2~3 名 + 具体代价说明（成本 / 工艺 / 耐温差异）。"""
    out = []
    for other in ranked[idx + 1: idx + 3]:
        m = other["material"]
        costs = []
        p1, p2 = top["material"].get("price_max"), m.get("price_max")
        if p1 and p2:
            diff = (float(p2) - float(p1)) / float(p1) * 100
            if abs(diff) >= 5:
                costs.append(f"成本{'高' if diff > 0 else '低'} {abs(diff):.0f}%")
        l1, l2 = top["material"].get("service_temp_limit"), m.get("service_temp_limit")
        if l1 and l2 and l1 != l2:
            costs.append(f"耐温上限 {'+' if l2 > l1 else ''}{int(l2 - l1)} °C")
        if costs:
            note = "、".join(costs)
        else:
            note = "综合性能接近"
        out.append({"name": m.get("name") or "", "score": int(round(other["score"])), "tradeoff": note})
    return out


# ---------------------------------------------------------------- 对外：run


def run(constraints: dict, task_id: Optional[int] = None, user_text: str = "") -> dict:
    """第 ②③④ 段。返回 {results, degraded, relaxed}。"""
    constraints = constraints or {}
    weights = get_weights_fraction()
    penalty_cfg = get_penalty()
    dim_weights = get_penalty_dim_weights()

    user_text = (user_text or "").strip()
    has_scene_text = bool(user_text)
    if not has_scene_text:
        user_text = " ".join(
            str(x) for x in (
                constraints.get("part_type"), constraints.get("process"),
                *(constraints.get("extra") or []),
            ) if x
        )

    relaxed: List[str] = []
    candidates = _hard_filter(constraints)

    # 空结果 → 放宽温度 10 度重试（PRD B1 降级；绝不返回空列表给前端）
    # 契约 §5.2：relaxed 记录「放宽项」本身；即便放宽后仍为空也必须记录，
    # 否则前端无法向用户解释「为什么放宽了还没有结果」。
    if not candidates and constraints.get("temp_limit") is not None:
        original = float(constraints["temp_limit"])
        relaxed_temp = max(0.0, original - 10.0)
        candidates = _hard_filter(constraints, temp_override=relaxed_temp)
        relaxed.append(f"已放宽温度至 {int(relaxed_temp)} °C")

    if not candidates:
        return {"results": [], "degraded": True, "relaxed": relaxed}

    ids = [material_repo.get_material_id(c["uid"]) for c in candidates]
    hits_map = hits_for_materials([i for i in ids if i is not None])
    id_to_uid = {i: c["uid"] for i, c in zip(ids, candidates)}

    cost_sensitive = "低成本" in (constraints.get("extra") or [])
    ranked = []
    for card in candidates:
        mid = material_repo.get_material_id(card["uid"])
        s_temp = _temp_score(card.get("service_temp_limit"), constraints.get("temp_limit"))
        s_sem = _semantic_score(user_text, card) if has_scene_text else SEMANTIC_NEUTRAL
        s_cost = _cost_score(card, cost_sensitive)
        s_mech = _mechanics_score(card, constraints.get("part_type"))
        s_proc = _process_score(card, constraints.get("process"))

        parts = {
            "temp": s_temp, "semantic": s_sem, "cost": s_cost,
            "mechanics": s_mech, "process": s_proc,
        }
        raw = sum(weights.get(k, 0.0) * v for k, v in parts.items()) * 100.0
        pen = _feedback_penalty(
            hits_map.get(mid, {}), dim_weights,
            penalty_cfg["threshold"], penalty_cfg["max"],
        )
        total = max(0.0, raw - pen)

        breakdown = {
            k: {"got": round(v * weights.get(k, 0.0) * 100, 1),
                "max": round(weights.get(k, 0.0) * 100, 1)}
            for k, v in parts.items()
        }
        breakdown["feedback_penalty"] = -pen if pen else 0
        ranked.append({"material": card, "score": total, "breakdown": breakdown,
                       "_pen": pen, "_dims": parts})

    ranked.sort(key=lambda r: r["score"], reverse=True)
    ranked = [r for r in ranked if r["score"] >= 60][:5]

    if not ranked:
        # 全部低于 60 分阈值：视为无合适材料，交由前端展示优化提示（不放宽不返回）
        return {"results": [], "degraded": True, "relaxed": relaxed}

    top = ranked[0]
    results = []
    for i, item in enumerate(ranked):
        m = item["material"]
        results.append({
            "material": m,
            "score": int(round(item["score"])),
            "breakdown": item["breakdown"],
            "reason": build_reason(m, constraints, item.get("_dims") or {}, item["_pen"]),
            "key_params": build_key_params(m),
            "cautions": [c.get("content", "") for c in (m.get("cautions") or []) if isinstance(c, dict)],
            "alternatives": _build_alternatives(ranked, i, top),
        })
    return {"results": results, "degraded": False, "relaxed": relaxed}
