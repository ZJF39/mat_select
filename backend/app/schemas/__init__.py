"""Pydantic 模型：请求体与响应体，字段名与前端 TS（doc/前端原型/04）1:1 对应。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------- 枚举 ----------------
class ValueType(str):
    typical = "typical"
    guaranteed = "guaranteed"


# ---------------- 材料 ----------------
class Certification(BaseModel):
    ul94: Optional[str] = None
    ul_yellow_card: Optional[str] = None
    rohs: Optional[bool] = None
    reach: Optional[bool] = None
    iatf: Optional[str] = None


class Caution(BaseModel):
    type: str = ""
    content: str = ""


class Categorization(BaseModel):
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    category_path: List[str] = Field(default_factory=list)
    grade_type: Optional[str] = None


class MaterialCard(Categorization):
    uid: str
    name: str
    short_name: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    density_min: Optional[float] = None
    density_max: Optional[float] = None
    service_temp_limit: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_unit: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    molding_process: List[str] = Field(default_factory=list)
    archived: bool = False


class MaterialDetail(MaterialCard):
    description: Optional[str] = None
    tensile_strength_min: Optional[float] = None
    tensile_strength_max: Optional[float] = None
    elastic_modulus_min: Optional[float] = None
    elastic_modulus_max: Optional[float] = None
    elongation_min: Optional[float] = None
    elongation_max: Optional[float] = None
    notch_impact_min: Optional[float] = None
    notch_impact_max: Optional[float] = None
    hdt_min: Optional[float] = None
    hdt_max: Optional[float] = None
    service_temp_min: Optional[float] = None
    service_temp_max: Optional[float] = None
    cautions: List[Caution] = Field(default_factory=list)
    applications: List[str] = Field(default_factory=list)
    price_note: Optional[str] = None
    certifications: Certification = Field(default_factory=Certification)
    limitations: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    source_date: Optional[str] = None
    value_type: str = "typical"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    negative_feedback: List[dict] = Field(default_factory=list)
    recent_revisions: List[dict] = Field(default_factory=list)


class MaterialUpsert(BaseModel):
    """新建 / 更新材料请求体（只读字段不接收）。"""
    name: str
    short_name: Optional[str] = None
    category_id: Optional[int] = None
    grade_type: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    density_min: Optional[float] = None
    density_max: Optional[float] = None
    tensile_strength_min: Optional[float] = None
    tensile_strength_max: Optional[float] = None
    elastic_modulus_min: Optional[float] = None
    elastic_modulus_max: Optional[float] = None
    elongation_min: Optional[float] = None
    elongation_max: Optional[float] = None
    notch_impact_min: Optional[float] = None
    notch_impact_max: Optional[float] = None
    hdt_min: Optional[float] = None
    hdt_max: Optional[float] = None
    service_temp_min: Optional[float] = None
    service_temp_max: Optional[float] = None
    service_temp_limit: Optional[float] = None
    features: List[str] = Field(default_factory=list)
    cautions: List[Caution] = Field(default_factory=list)
    applications: List[str] = Field(default_factory=list)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_unit: Optional[str] = None
    price_note: Optional[str] = None
    molding_process: List[str] = Field(default_factory=list)
    certifications: Optional[Certification] = None
    limitations: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    source_date: Optional[str] = None
    value_type: str = "typical"


# ---------------- 分类 ----------------
class CategoryNode(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    sort_order: int = 0
    created_at: Optional[str] = None
    count: int = 0
    children: List["CategoryNode"] = Field(default_factory=list)


class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class CategoryPatch(BaseModel):
    name: Optional[str] = None


# ---------------- 推荐 ----------------
class Constraints(BaseModel):
    part_type: Optional[str] = None
    process: Optional[str] = None
    temp_limit: Optional[float] = None
    extra: List[str] = Field(default_factory=list)


class ParseRequest(BaseModel):
    text: str = ""
    task_id: Optional[int] = None


class RecommendRequest(BaseModel):
    constraints: Constraints
    task_id: Optional[int] = None


class ScorePart(BaseModel):
    got: float
    max: float = 100


class ScoreBreakdown(BaseModel):
    temp: ScorePart = Field(default_factory=lambda: ScorePart(got=0))
    semantic: ScorePart = Field(default_factory=lambda: ScorePart(got=0))
    cost: ScorePart = Field(default_factory=lambda: ScorePart(got=0))
    mechanics: ScorePart = Field(default_factory=lambda: ScorePart(got=0))
    process: ScorePart = Field(default_factory=lambda: ScorePart(got=0))
    feedback_penalty: float = 0


class Alternative(BaseModel):
    name: str
    score: int
    tradeoff: str


class Recommendation(BaseModel):
    material: dict
    score: int
    breakdown: ScoreBreakdown
    reason: str
    key_params: List[str] = Field(default_factory=list)
    cautions: List[str] = Field(default_factory=list)
    alternatives: List[Alternative] = Field(default_factory=list)


# ---------------- 任务 / 会话 ----------------
class TaskMessageCreate(BaseModel):
    text: str = ""


class TaskPatch(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    status: Optional[str] = None


class TaskMessage(BaseModel):
    id: int
    role: str
    created_at: Optional[str] = None
    text: Optional[str] = None
    constraints: Optional[Constraints] = None
    confidence: Optional[float] = None
    degraded: Optional[bool] = None
    results: Optional[List[dict]] = None
    relax_note: Optional[str] = None
    reweight_note: Optional[str] = None


class SelectionTask(BaseModel):
    id: int
    title: str
    pinned: bool = False
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    recommendation_count: int = 0
    shortlist_count: int = 0


# ---------------- 待选 ----------------
class ShortlistAdd(BaseModel):
    material_uid: str
    tag: Optional[str] = "candidate"


class ShortlistPatch(BaseModel):
    user_note: Optional[str] = None
    tag: Optional[str] = None


class ShortlistOrder(BaseModel):
    ids: List[int] = Field(default_factory=list)


class ShortlistItem(BaseModel):
    id: int
    material: dict
    score: float = 0
    user_note: str = ""
    tag: str = "candidate"
    sort_order: int = 0
    added_at: Optional[str] = None


# ---------------- 回评 ----------------
class FeedbackPayload(BaseModel):
    result: str  # success | fail | skipped
    reason_text: Optional[str] = None
    reason_tags: List[str] = Field(default_factory=list)
    material_uids: List[str] = Field(default_factory=list)


class FeedbackParseResult(BaseModel):
    materials: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    confidence: float = 0


class FeedbackResponse(BaseModel):
    parsed: FeedbackParseResult
    penalty_applied: bool
    feedback_id: int = 0


# ---------------- 知识盲区 ----------------
class GapItem(BaseModel):
    dimension: str
    count: int
    suggestion: str


# ---------------- 设置 / 权重 / 降权 ----------------
class WeightItem(BaseModel):
    key: str
    label: str
    weight: float
    hint: str


class PenaltyConfig(BaseModel):
    threshold: int
    max: int


class SettingsWeights(BaseModel):
    dims: List[WeightItem] = Field(default_factory=list)
    penalty: PenaltyConfig = Field(default_factory=lambda: PenaltyConfig(threshold=2, max=15))
    sum: float = 0


class WeightUpdateItem(BaseModel):
    key: str
    weight: float


class SettingsWeightsUpdate(BaseModel):
    dims: List[WeightUpdateItem] = Field(default_factory=list)
    penalty: Optional[PenaltyConfig] = None


# ---------------- 日志 / 搜索 / 备份 ----------------
class LogItem(BaseModel):
    at: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None


class SearchResult(BaseModel):
    materials: List[dict] = Field(default_factory=list)
    tasks: List[dict] = Field(default_factory=list)
    scenes: List[str] = Field(default_factory=list)


class BackupStatus(BaseModel):
    last_backup_at: Optional[str] = None
    location: str = ""


# ---------------- 变更历史 / diff ----------------
class Revision(BaseModel):
    version: int
    changed_at: Optional[str] = None
    change_note: Optional[str] = None


class DiffRow(BaseModel):
    field: str
    key: str
    type: str  # add | remove | modify
    before: Optional[str] = None
    after: Optional[str] = None
    before_items: List[str] = Field(default_factory=list)
    after_items: List[str] = Field(default_factory=list)


class DiffPayload(BaseModel):
    from_version: int
    to_version: int
    summary: str
    rows: List[DiffRow] = Field(default_factory=list)


# ---------------- 导出 / 导入 ----------------
class ExportRequest(BaseModel):
    scope: str = "all"  # all | filtered | selected | shortlist
    format: str = "json"  # json | xlsx | md
    include_work_data: bool = False
    ids: List[str] = Field(default_factory=list)
    task_id: Optional[int] = None
    dbg: Optional[dict] = None
    # filtered 范围继承的检索条件
    q: Optional[str] = None
    category_ids: Optional[str] = None
    processes: Optional[str] = None
    temp_min: Optional[float] = None
    price_max: Optional[float] = None
    flame: Optional[str] = None
    features: Optional[str] = None
    sort: Optional[str] = None
    order: Optional[str] = None


class ImportCommit(BaseModel):
    token: str
    conflict_policy: str = "skip"  # skip | overwrite | duplicate


class ImportDetail(BaseModel):
    uid: Optional[str] = None
    name: str = ""
    kind: str  # add | update | conflict | invalid
    reason: Optional[str] = None


class ImportPreview(BaseModel):
    token: str
    pack_version: int = 1
    exported_by: str = ""
    exported_at: str = ""
    checksum_ok: bool = False
    added: int = 0
    updated: int = 0
    conflicted: int = 0
    invalid: int = 0
    details: List[ImportDetail] = Field(default_factory=list)


class ImportResult(BaseModel):
    ok: bool = True
    added: int = 0
    updated: int = 0
    conflicted: int = 0
    skipped: int = 0
    total: int = 0
    message: str = ""


CategoryNode.model_rebuild()
