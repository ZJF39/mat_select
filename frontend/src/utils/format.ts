/**
 * 展示层格式化工具（原型 04 §5「前端必须自己算的展示逻辑」）
 * 归属：技术负责人（冻结）。页面禁止自行实现另一套规则。
 */
import type { ShortlistTag } from '../api/types'

/** 区间显示：两者都有 → a–b；仅 max → ≤ b（温度类）/ b（价格类）；都没有 → — */
export function formatRange(
  min: number | null | undefined,
  max: number | null | undefined,
  mode: 'temp' | 'plain' = 'plain',
): string {
  const hasMin = min !== null && min !== undefined
  const hasMax = max !== null && max !== undefined
  if (hasMin && hasMax) return min === max ? String(min) : `${min}–${max}`
  if (hasMax) return mode === 'temp' ? `≤ ${max}` : String(max)
  if (hasMin) return `≥ ${min}`
  return '—'
}

/** 单值显示（如 service_temp_limit） */
export function formatValue(v: number | null | undefined, unit?: string): string {
  if (v === null || v === undefined) return '—'
  return unit ? `${v} ${unit}` : String(v)
}

export function isNil(v: unknown): boolean {
  return v === null || v === undefined || v === ''
}

/** 相对时间：<1天 → 刚刚/n小时前；<7天 → 昨天/周X；否则 MM-DD */
export function formatTime(iso: string | null | undefined, full = false): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  const ymd = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (full) return `${ymd} ${hm}`
  const diff = Date.now() - d.getTime()
  const day = 86_400_000
  if (diff < 60_000) return '刚刚'
  if (diff < day && d.getDate() === new Date().getDate()) return `${Math.floor(diff / 3_600_000)} 小时前`
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  if (diff < 7 * day) {
    const yesterday = new Date(Date.now() - day)
    if (d.toDateString() === yesterday.toDateString()) return '昨天'
    return week[d.getDay()]
  }
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 待选标记文案（双编码：文字 + 颜色） */
export const TAG_LABEL: Record<ShortlistTag, string> = {
  key: '重点考虑',
  pending: '待验证',
  rejected: '已淘汰',
  candidate: '待定',
}

export const TAG_TONE: Record<ShortlistTag, string> = {
  key: 'ms-chip--accent',
  pending: 'ms-chip--warning',
  rejected: '',
  candidate: '',
}

/** 价格展示：min–max + 单位 */
export function formatPrice(
  min: number | null | undefined,
  max: number | null | undefined,
  unit: string | null | undefined,
): string {
  const r = formatRange(min, max, 'plain')
  if (r === '—') return '—'
  return unit ? `${r} ${unit}` : r
}

/** 匹配度 ← score */
export function pct(score: number): string {
  return `${Math.round(score)}%`
}

/** 材料名截断：>12 字保留全部（卡片允许 2 行），别名行单行省略 */
export function ellipsisAliases(aliases: string[] | null | undefined, n = 2): string {
  if (!aliases || aliases.length === 0) return ''
  return aliases.slice(0, n).join('、')
}
