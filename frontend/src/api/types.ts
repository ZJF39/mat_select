/**
 * MatSelect 前端类型定义
 * 来源：doc/前端原型/04-字段与接口映射.md §4（1:1 对齐）+ 契约 §4 补充
 * 规则：字段名 = 后端 Pydantic 字段名 = DDL 列名；缺失一律 null，不用空字符串。
 */

/* ---------- 材料 ---------- */
export type ValueType = 'typical' | 'guaranteed'

export interface Categorization {
  category_id: number | null
  category_name: string | null
  category_path: string[]
  grade_type?: string | null
}

export interface Certification {
  ul94?: string | null
  ul_yellow_card?: string | null
  rohs?: boolean | null
  reach?: boolean | null
  iatf?: string | null
}

export interface Caution {
  type: string
  content: string
}

export interface MaterialCard extends Categorization {
  uid: string
  name: string
  short_name?: string | null
  aliases: string[]
  density_min: number | null
  density_max: number | null
  service_temp_limit: number | null
  price_min: number | null
  price_max: number | null
  price_unit: string | null
  features: string[]
  molding_process: string[]
  archived?: boolean
}

export interface MaterialDetail extends MaterialCard {
  description?: string | null
  tensile_strength_min: number | null
  tensile_strength_max: number | null
  elastic_modulus_min: number | null
  elastic_modulus_max: number | null
  elongation_min: number | null
  elongation_max: number | null
  notch_impact_min: number | null
  notch_impact_max: number | null
  hdt_min: number | null
  hdt_max: number | null
  service_temp_min: number | null
  service_temp_max: number | null
  cautions: Caution[]
  applications: string[]
  price_note?: string | null
  certifications: Certification
  limitations: string[]
  source?: string | null
  source_date?: string | null
  value_type: ValueType
  created_at: string
  updated_at: string
  negative_feedback?: { dimension: string; count: number; active: boolean }[]
  recent_revisions?: { changed_at: string; summary: string }[]
}

/** 新建 / 编辑提交体（uid / 时间由后端维护） */
export interface MaterialUpsert {
  name: string
  short_name?: string | null
  category_id?: number | null
  grade_type?: string | null
  aliases?: string[]
  description?: string | null
  density_min?: number | null
  density_max?: number | null
  tensile_strength_min?: number | null
  tensile_strength_max?: number | null
  elastic_modulus_min?: number | null
  elastic_modulus_max?: number | null
  elongation_min?: number | null
  elongation_max?: number | null
  notch_impact_min?: number | null
  notch_impact_max?: number | null
  hdt_min?: number | null
  hdt_max?: number | null
  service_temp_min?: number | null
  service_temp_max?: number | null
  service_temp_limit?: number | null
  features?: string[]
  cautions?: Caution[]
  applications?: string[]
  price_min?: number | null
  price_max?: number | null
  price_unit?: string | null
  price_note?: string | null
  molding_process?: string[]
  certifications?: Certification
  limitations?: string[]
  source?: string | null
  source_date?: string | null
  value_type?: ValueType
}

export interface CategoryNode {
  id: number
  name: string
  parent_id: number | null
  count: number
  children?: CategoryNode[]
}

export interface Revision {
  id: number
  version: number
  changed_at: string
  change_note?: string | null
  summary: string
}

export interface DiffRow {
  field: string
  key: string
  type: 'add' | 'remove' | 'modify'
  before: string | null
  after: string | null
  before_items: string[]
  after_items: string[]
}

export interface DiffPayload {
  from_version: number
  to_version: number
  summary: string
  rows: DiffRow[]
}

/* ---------- 推荐 ---------- */
export interface Constraints {
  part_type?: string | null
  process?: string | null
  temp_limit?: number | null
  extra: string[]
}

export interface ScoreBreakdown {
  temp: { got: number; max: number }
  semantic: { got: number; max: number }
  cost: { got: number; max: number }
  mechanics: { got: number; max: number }
  process: { got: number; max: number }
  feedback_penalty: number
}

export interface Recommendation {
  material: MaterialCard
  score: number
  breakdown: ScoreBreakdown
  reason: string
  key_params: string[]
  cautions: string[]
  alternatives: { name: string; score: number; tradeoff: string }[]
}

export interface ParseResult {
  constraints: Constraints
  confidence: number
  degraded: boolean
  raw_text: string
}

/* ---------- 任务 / 会话 ---------- */
export type MessageRole = 'user' | 'assistant'

export interface TaskMessage {
  id: number
  role: MessageRole
  created_at: string
  text?: string
  constraints?: Constraints
  confidence?: number
  degraded?: boolean
  results?: Recommendation[]
  relax_note?: string
  reweight_note?: string
}

export interface SelectionTask {
  id: number
  title: string
  pinned: boolean
  status: 'active' | 'archived'
  created_at: string
  updated_at: string
  recommendation_count: number
  shortlist_count: number
}

/* ---------- 待选 / 回评 ---------- */
export type ShortlistTag = 'key' | 'pending' | 'rejected' | 'candidate'

export interface ShortlistItem {
  id: number
  material: MaterialCard
  score: number
  user_note: string
  tag: ShortlistTag
  sort_order: number
  added_at: string
}

export type FeedbackResult = 'success' | 'fail' | 'skipped'

export interface FeedbackPayload {
  result: FeedbackResult
  reason_text?: string
  reason_tags?: string[]
  material_uids?: string[]
}

export interface ParsedReason {
  materials: string[]
  dimensions: string[]
  keywords: string[]
  confidence: number
}

export interface FeedbackRecord extends FeedbackPayload {
  id: number
  task_id: number
  created_at: string
  parsed_reason?: ParsedReason | null
}

/* ---------- 导出包（E1/E2 交换格式） ---------- */
export interface MaterialPack {
  pack_version: 1
  exported_at: string
  exported_by: string
  material_count: number
  checksum: string
  materials: MaterialDetail[]
  work_data?: {
    tasks: SelectionTask[]
    messages: TaskMessage[]
    shortlist: ShortlistItem[]
    feedback: FeedbackPayload[]
  }
}

export interface ImportDetail {
  uid: string
  name: string
  kind: 'add' | 'update' | 'conflict' | 'invalid'
  reason?: string
}

export interface ImportPreview {
  token: string
  pack_version: number
  exported_by: string
  exported_at: string
  checksum_ok: boolean
  added: number
  updated: number
  conflicted: number
  invalid: number
  details: ImportDetail[]
}

export interface ImportResult {
  ok: boolean
  added: number
  updated: number
  skipped: number
  duplicated: number
  message: string
}

/* ---------- 设置 / 系统 ---------- */
export interface WeightDim {
  key: string
  label: string
  weight: number
  hint: string
}

export interface WeightsConfig {
  dims: WeightDim[]
  penalty: { threshold: number; max: number }
  sum: number
}

export interface LogEntry {
  at: string
  action: string
  target: string
}

export interface SearchResult {
  materials: MaterialCard[]
  tasks: SelectionTask[]
  scenes: string[]
}

export interface BackupStatus {
  last_backup_at: string | null
  location: string
}

export interface GapInsight {
  dimension: string
  count: number
  suggestion: string
}

export interface NegativeFeedbackRow {
  material_uid: string
  material_name: string
  dimension: string
  hit_count: number
  active: boolean
}
