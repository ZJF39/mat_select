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
    # 传动/承力件此前未归类，会落到默认力学规格（强度/耐温/耐磨/易成型），
    # 使「齿轮」等耐磨件被通用规格里的强度、耐温项主导（实测 POM 因只命中
    # 「耐磨」拿保底 0.3，而 PA66 命中强度+耐温+耐磨拿 0.8，齿轮首选被夺走）。
    "齿轮": "结构件", "传动件": "结构件", "蜗轮": "结构件", "蜗杆": "结构件",
    "齿条": "结构件", "链轮": "结构件", "轴承": "结构件", "轴套": "结构件",
    "滑块": "结构件", "凸轮": "结构件",
    "卡扣": "外观件", "卡子": "外观件", "clip": "外观件",
    "出风口": "外观件", "风道": "外观件", "装饰件": "外观件", "面板": "外观件",
    "仪表板": "外观件", "仪表盘": "外观件", "内饰件": "外观件", "格栅": "外观件",
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

# 力学维度：按零件类型给特性关键词加权（契约 §5.3「按零件类型推断典型力学需求」）
# 结构件补入「耐磨」，默认规格补入「耐磨」：耐磨 / 自润滑是传动件（齿轮、轴承）
# 的核心力学诉求，此前不在任何规格内，用户明说「耐磨自润滑」时力学维度仍无法响应。
_MECHANICS_BY_PART = {
    "电气件": (("阻燃", 0.4), ("绝缘", 0.3), ("耐温", 0.15), ("强度", 0.15)),
    "结构件": (("强度", 0.35), ("刚性", 0.2), ("抗蠕变", 0.15), ("耐温", 0.15), ("耐磨", 0.15)),
    # 外观件原含 ("成本", 0.2)：成本已由独立的成本维度（20% 权重）承载，
    # 在力学维度再计一次属重复计分，且使「外观件」的力学分变成价格排序。
    # 改为「抗冲」——内外饰件的典型力学诉求（实测「仪表板内饰件，要耐冲击」
    # 因该信号缺失，被最便宜但韧性差的 PP 挤到首位）。
    "外观件": (("易成型", 0.3), ("表面", 0.25), ("抗冲", 0.25), ("密度", 0.2)),
    None: (("强度", 0.35), ("耐温", 0.25), ("耐磨", 0.2), ("易成型", 0.2)),
}

# 力学维度关键词的同义词组。
# 必要性：维度名与数据侧用词并不一致（维度「耐温」，数据写「耐热」；维度「刚性」，
# 数据写「高刚性」），原实现用精确子串比对会整项漏判 —— 实测 PA66+GF30 因
# features 写「耐热」而非「耐温」，电气件的耐温权重 0.15 被直接丢弃。
_FEATURE_SYNONYMS = {
    "阻燃": ("阻燃", "防火", "难燃", "离火自熄"),
    "绝缘": ("绝缘", "介电", "电气绝缘"),
    "耐温": ("耐温", "耐热", "耐高温", "热稳定", "长期使用温度"),
    "强度": ("强度", "抗拉", "拉伸强度"),
    "刚性": ("刚性", "挺度", "模量"),
    "抗蠕变": ("抗蠕变", "蠕变"),
    "易成型": ("易成型", "流动性", "成型"),
    "表面": ("表面", "外观", "光洁"),
    "密度": ("密度", "轻量", "轻质"),
    "成本": ("成本", "低价", "经济", "便宜"),
    "耐磨": ("耐磨", "自润滑", "耐磨损", "低摩擦", "磨耗", "润滑"),
    "抗冲": ("抗冲", "冲击", "高冲击", "耐冲击", "抗冲击", "韧性"),
}

# 「玻纤 / 碳纤增强」是材料力学强度的**结构化信号**：牌号里的 GF30 / GF40 本身
# 即代表增强倍数，不应依赖 features 是否恰好写了「强度」二字。实测 PPS+GF40 的
# features 只写「高刚性」未写「强度」，强度项（结构件权重 0.35）被整项丢弃、
# 力学分仅 0.35，反不如未增强却写了「高强度」的 PPA（0.6），40% 玻纤增强材料
# 在结构件维度屈居末位。
_REINFORCE_RE = re.compile(r"玻纤|碳纤|玻璃纤维|碳纤维|gf\s*\d+|cf\s*\d+", re.IGNORECASE)


def _is_reinforced(material: dict) -> bool:
    """材料是否为纤维增强（名称 / 描述 / 别名中出现玻纤、碳纤或 GF/CF 牌号）。"""
    text = " ".join(str(x) for x in (
        material.get("name"), material.get("short_name"),
        material.get("description"), *(material.get("aliases") or []),
    ) if x)
    return bool(_REINFORCE_RE.search(text))

# 视作「具备阻燃性」的 UL94 级别。阻燃是结构化认证字段，不应依赖 features
# 是否恰好写了「阻燃」二字 —— 实测 PA66+GF30 认证为 V-0，却因 features 未写
# 「阻燃」而在电气件维度丢掉 0.4 权重。
_FLAME_CERT_VALUES = ("v-0", "v0", "v1", "v-1", "5va", "5vb")

# 领域同义词组：把「同一概念的不同叫法」归组，供术语命中判定使用。
# 必要性：材料数据的用词与用户提问用词天然不一致 —— 用户说「灯罩」，PC 记录写
# 的是「透明罩 / 灯壳」；用户说「低成本」，PS 记录写的是「成本低」。字面精确
# 匹配会让语义分取决于**用词巧合**而非材料实质：实测 PC 仅因「灯罩」未命中，
# 语义拿 0.5、总分 59.9 被 60 分门槛淘汰，而它恰是车灯罩的主流材料。
# 本模块的设计前提即「规则 + 词典 + 正则为主，不做开放式语义理解」（PRD §5.4），
# 故以词典补齐同义表达符合设计意图。
_DOMAIN_SYNONYM_GROUPS = (
    # —— 部件 / 应用名词 ——
    ("灯罩", "灯壳", "透明罩", "指示灯透镜", "透镜", "灯座"),
    ("外壳", "壳体", "小壳体", "电子外壳", "电气外壳", "小家电外壳", "电池壳", "机壳"),
    ("密封圈", "O型圈", "油封", "密封", "高温密封", "密封条", "垫圈"),
    ("连接器", "接插件", "特种连接器", "高温连接器", "高频连接器",
     "表面贴装连接器", "端子", "插座", "接头", "弹片"),
    ("齿轮", "传动件"),
    ("轴承", "衬套", "滑块"),
    ("支架", "传感器支架", "结构支架", "支座", "LED支架", "底座"),
    ("卡扣", "内饰卡扣", "紧固件", "扎带"),
    ("覆盖件", "车身板", "车身件", "加强板", "钣金件"),
    ("端盖", "罩盖"),
    ("绝缘件", "高温绝缘件", "绝缘子"),
    ("线束护套", "护套", "线缆包覆", "包覆"),
    ("空调出风口", "暖风出风口", "出风口", "风道"),
    # —— 性能 / 特性词 ——
    ("透明", "透光", "透明可选", "透明(瓶级)"),
    ("低成本", "成本低", "低价", "经济"),
    ("阻燃", "阻燃性好", "防火", "难燃"),
    ("耐热", "耐温", "耐热好", "耐热中", "耐高温", "超耐热", "超高耐热",
     "高耐热", "耐高低温", "热稳定"),
    ("高强度", "强度高", "高刚性", "超高刚性", "刚度高", "刚性好", "刚性"),
    ("耐磨", "自润滑"),
    ("高冲击", "韧性", "韧性好", "耐冲击", "抗冲击", "抗冲"),
    ("耐化学", "耐化学性", "耐化学性好", "耐腐蚀", "耐油", "耐油中"),
    ("耐候", "耐候性好"),
    ("绝缘", "电绝缘", "电性好", "介电"),
    ("轻量", "密度小", "超轻高强", "轻质"),
    ("尺寸稳定", "尺寸好", "低收缩", "低翘曲"),
    ("易成型", "高流动", "成型快", "流动性", "量产好"),
    ("表面好", "表面硬度高", "美观", "外观", "光洁"),
)


def _build_synonym_index(groups) -> dict:
    """构建对称反向索引：任一成员 → 其所在组的全部成员。"""
    idx: dict = {}
    for group in groups:
        for word in group:
            idx.setdefault(word, set()).update(group)
    return idx


_DOMAIN_SYNONYM_INDEX = _build_synonym_index(_DOMAIN_SYNONYM_GROUPS)


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


# 语义维度补充信号：用户文本中的「零件类型词」是否命中材料的归属字段
# （名称 / 简称 / 别名 / 典型应用 / 概述）。
# 必要性（实测缺陷）：单靠字符 bigram 余弦时，需求长文本 vs 材料长文本的
# 绝对相似度天然只有 0~0.07（分母被长文本放大），25% 权重的语义维度实际
# 失去区分度 —— 「用户明说保险丝座、某材料 applications 恰好含保险丝座」
# 这种最强领域信号也被稀释成不足 1 分（实测 PA66+GF30 语义 0.031/1.0）。
# 故在本维度内叠加术语命中项，量纲仍为 0~1，五维契约与分解恒等式不变。
_TERM_WEIGHT = 0.75
_COS_WEIGHT = 0.25
_COS_SCALE = 4.0


def _term_vocabulary(materials: List[dict]) -> List[str]:
    """构建「可锚定术语」词表：零件类型词典 ∪ 候选材料的别名 / 典型应用 / 特性。

    必要性：原实现只认 `PART_TYPE_DICT` 里 36 个预设零件名，用户一旦改用应用件
    名词（齿轮 / 灯罩 / 密封圈 / 端盖）或性能词（耐磨 / 透光 / 散热），术语信号
    即整体失效、语义维度塌回 ~0，总分跌破 60 分门槛 → **返回空结果**。实测
    「齿轮，注塑，要耐磨自润滑」即因此被判定为无合适材料，而库中 `POM` 的
    applications 恰好写着「齿轮」。

    词表改由**材料数据自身**派生后，「齿轮」自动锚定到 applications 含「齿轮」
    的材料，无需人工枚举领域词。
    """
    vocab = set(PART_TYPE_DICT)
    for m in materials or []:
        for field in ("aliases", "applications", "features"):
            for v in (m.get(field) or []):
                s = str(v).strip()
                if len(s) >= 2:
                    vocab.add(s)
    return sorted(vocab, key=len, reverse=True)


def _concept_key(term: str):
    """术语所属「概念」的标识：落在同义组内则用整组为键，否则用术语自身。

    用于把「耐热 / 耐温 / 超耐热 / 超耐热…」等同组词折叠成一个代表术语，
    避免同组词互相命中把术语数虚增、稀释真正的领域信号。
    """
    group = _DOMAIN_SYNONYM_INDEX.get(term)
    return frozenset(group) if group else term


def _matched_terms(user_text: str, vocabulary: Optional[List[str]] = None) -> List[str]:
    """从用户文本中识别可作为「材料归属」锚点的领域术语。

    `vocabulary` 为 None 时退回仅零件类型词典（兼容旧调用方）。

    命中判定走**同义词组**而非字面比对：词表条目取自材料数据（如 `PC-ABS` 的
    「高冲击」），用户措辞几乎不会逐字相同（「要耐冲击」）。原实现只做字面子串
    比对，导致这类诉求整条丢失 —— 实测「仪表板内饰件，要耐冲击」识别不出任何
    冲击相关术语，「耐冲击」这一**显式诉求被完全忽略**，排序退化为价格排序。

    同组术语按 `_concept_key` 折叠，只保留一个代表。
    """
    vocab = vocabulary if vocabulary is not None else list(PART_TYPE_DICT)
    low = (user_text or "").lower()
    out: List[str] = []
    seen = set()
    for t in vocab:
        if not t or len(t) < 2:
            continue
        if not any(s.lower() in low for s in _term_synonyms(t)):
            continue
        key = _concept_key(t)
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _term_synonyms(term: str) -> tuple:
    """术语的同义/等价表达：额外约束组 ∪ 特性组 ∪ 领域组 ∪ 术语自身。

    与 `_mechanics_score` 共用同一套词典口径，避免「阻燃」在同一份打分里
    被力学维度认、却被语义维度否掉的内部矛盾。
    """
    syns = list(EXTRA_KEYWORDS.get(term) or [])
    syns += list(_FEATURE_SYNONYMS.get(term) or ())
    syns += sorted(_DOMAIN_SYNONYM_INDEX.get(term) or ())
    return tuple(dict.fromkeys([term, *syns]))


def _material_blob(material: dict, low_cost: Optional[bool] = None) -> str:
    """材料可检索文本。除各自由文本字段外，把**结构化字段**归一到领域标签：

    - `certifications.ul94 = V-0` ⇒ 「阻燃」。不应因为 features 文案恰好没写
      「阻燃」二字而丢掉该信号（实测 PBT+GF30 认证 V-0，却因文案未提「阻燃」
      导致语义分 0.44 对 PES 0.83，被挤到第 3 名）。
    - 参考价 ≤ `_LOW_COST_PRICE` ⇒ 「成本低」。价格是**权威结构化数据**，不应
      要求 features 再写一遍「成本低」才认（实测 ABS 12–18 元/kg，因 features
      未写成本词，「低成本」术语命中率仅 1/2、语义分被腰斩，在「低成本普通外壳」
      场景跌出前五）。
    """
    parts = [
        str(material.get("name") or ""),
        str(material.get("short_name") or ""),
        " ".join(str(x) for x in (material.get("aliases") or [])),
        " ".join(str(x) for x in (material.get("applications") or [])),
        " ".join(str(x) for x in (material.get("features") or [])),
        str(material.get("description") or ""),
    ]
    certs = material.get("certifications") or {}
    if str((certs or {}).get("ul94") or "").strip().lower() in _FLAME_CERT_VALUES:
        parts.append("阻燃")
    if low_cost is None:
        price = material.get("price_max")
        if price is None:
            price = material.get("price_min")
        low_cost = price is not None and float(price) <= _LOW_COST_PRICE
    if low_cost:
        parts.append("成本低")
    return " ".join(p for p in parts if p).lower()


def _term_hit_score(terms: List[str], material: dict,
                    blob: Optional[str] = None) -> Optional[float]:
    """术语命中率 = 命中数 / 术语数；无可依据术语时返回 None（该维度不可评价）。

    每个术语按其**同义词组**匹配，而非字面精确匹配：材料描述同一概念用词
    并不统一（「低成本」/「成本低」、「透明」/「透光」），字面比对会让语义分
    取决于用词巧合而非材料实质。

    返回 None 而非 0.0 是关键：用户只说温度/工艺、未提任何领域术语时，
    若判为 0 会让全体材料语义分趋近 0，25% 权重足以把推荐主流程打空。
    """
    if not terms:
        return None
    text = blob if blob is not None else _material_blob(material)
    hits = sum(1 for t in terms if any(s.lower() in text for s in _term_synonyms(t)))
    return hits / float(len(terms))


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


def _semantic_score(user_text: str, material: dict,
                    terms: Optional[List[str]] = None) -> float:
    """语义近似 = 术语命中（主信号） + 字符 n-gram 余弦（辅信号，做尺度校准）。

    `terms` 由 `run()` 一次性算好传入，避免逐材料重复扫词表；未传时按旧行为
    从零件类型词典推导。无可依据术语时退回**纯余弦**：该场景下本维度事实上
    不可评价，不应给出人为基线，否则「未给出有效约束的输入」（闲聊）也会因
    中性分跨过 60 分门槛而产出推荐。
    """
    blob = _material_blob(material)
    hit_terms = _matched_terms(user_text) if terms is None else terms
    term = _term_hit_score(hit_terms, material, blob)
    if term is None:
        return similarity(user_text, blob)
    # 余弦实测取值区间约 0~0.15（长文本稀释），乘以 _COS_SCALE 拉回可用量纲
    cos_norm = min(1.0, similarity(user_text, blob) * _COS_SCALE)
    return min(1.0, _TERM_WEIGHT * term + _COS_WEIGHT * cos_norm)


# 材料参考价 ≤ 该值即视为「低成本」档，作为结构化标签参与术语命中
# （见 `_material_blob`）。依据库内价格分布：通用塑料 8~20、工程塑料 20~60、
# 特种工程塑料 60~600 元/kg，20 元/kg 是通用塑料与工程塑料的分界。
_LOW_COST_PRICE = 20.0

# 契约 §5.3：「若用户提到成本敏感，权重提升」。实现为成本权重 ×1.5 后整体
# 归一化 —— Σ=1 恒成立，五维加权分解恒等式（got 之和 = score）不被破坏。
_COST_SENSITIVE_BOOST = 1.5


def _cost_score(material: dict) -> float:
    """成本合理性：按参考价线性给分，越便宜越高；无价格信息给中性 0.5。

    契约 §5.3 定义成本维度为「20% 权重 = 相对场景的成本合理性」，并规定
    「若用户提到成本敏感，权重提升」（权重提升见 `_effective_weights`）。因此
    **未提成本 ≠ 成本无关**，该维度始终由参考价驱动。原实现「未提成本 → 全体
    恒定 0.6」会让 20% 权重退化成对每份材料等值的常数、对排序零贡献，等于把
    契约维度清零 —— 实测使 600 元/kg 的 PEEK 与 28 元/kg 的 POM 在「齿轮」场景
    经济性毫无差别，PEEK 反超成为首选。
    """
    price = material.get("price_max")
    if price is None:
        price = material.get("price_min")
    if price is None:
        return 0.5
    price = float(price)
    if price <= 15.0:
        return 1.0
    if price >= 80.0:
        return 0.2
    return 1.0 - 0.8 * (price - 15.0) / 65.0


def _effective_weights(cost_sensitive: bool) -> dict:
    """返回本次打分使用的五维权重（Σ=1）；成本敏感时提升成本维度权重。"""
    w = dict(get_weights_fraction())
    if not cost_sensitive:
        return w
    w["cost"] = float(w.get("cost", 0.0)) * _COST_SENSITIVE_BOOST
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def _mechanics_score(material: dict, part_type: Optional[str]) -> float:
    """力学匹配：按零件类型加权命中特性关键词。

    关键词一律走同义词组（`_FEATURE_SYNONYMS`），阻燃额外认结构化的 UL94
    认证字段（`certifications.ul94`），强度额外认牌号里的纤维增强标志
    （`_is_reinforced`，GF/CF 牌号），均不依赖 features 文案是否恰好用词一致。
    """
    spec = _MECHANICS_BY_PART.get(part_type, _MECHANICS_BY_PART[None])
    text = (" ".join(str(x) for x in (material.get("features") or []))
            + " " + str(material.get("description") or "")).lower()
    certs = material.get("certifications") or {}
    ul94 = str((certs or {}).get("ul94") or "").strip().lower()
    flame_by_cert = ul94 in _FLAME_CERT_VALUES
    reinforced = _is_reinforced(material)
    total = sum(w for _, w in spec) or 1.0
    got = 0.0
    for kw, w in spec:
        syns = _FEATURE_SYNONYMS.get(kw, (kw,))
        if (any(s.lower() in text for s in syns)
                or (kw == "阻燃" and flame_by_cert)
                or (kw == "强度" and reinforced)):
            got += w
    # 保底分改为**下限**而非「零命中加分」：原实现「零命中 +0.4」会出现
    # 「命中 1 项(0.15) 反而低于零命中(0.4)」的**非单调**——越契合规格的材料
    # 分数越低（实测 POM 因命中「刚性」反而比零命中材料少分）。
    return max(0.3, min(1.0, got / total))


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
    # 成本敏感（契约 §5.3）会提升成本维度权重，故权重须在约束抽取后计算
    cost_sensitive = "低成本" in (constraints.get("extra") or [])
    weights = _effective_weights(cost_sensitive)
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

    # 术语锚点一次性算好（词表由候选材料数据派生，见 _term_vocabulary）
    terms = _matched_terms(user_text, _term_vocabulary(candidates)) if has_scene_text else []
    ranked = []
    for card in candidates:
        mid = material_repo.get_material_id(card["uid"])
        s_temp = _temp_score(card.get("service_temp_limit"), constraints.get("temp_limit"))
        s_sem = _semantic_score(user_text, card, terms) if has_scene_text else SEMANTIC_NEUTRAL
        s_cost = _cost_score(card)
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
