import { useState } from 'react'
import { Chip } from './Chip'
import { Icon } from '../icons'
import { Skeleton } from './Skeleton'
import './ui.css'

export type ExportScope = 'all' | 'filtered' | 'selected' | 'shortlist'
export type ExportFormat = 'json' | 'xlsx' | 'md'

export interface ExportPanelProps {
  filteredCount?: number
  selectedCount?: number
  shortlistCount?: number
  totalCount?: number
  exporting?: boolean
  onExport: (body: {
    scope: ExportScope
    format: ExportFormat
    include_work_data: boolean
    ids?: string[]
  }) => void
}

const SCOPES: { value: ExportScope; label: string; count?: keyof ExportPanelProps }[] = [
  { value: 'all', label: '全部材料' },
  { value: 'filtered', label: '当前筛选结果' },
  { value: 'selected', label: '手动勾选的材料' },
  { value: 'shortlist', label: '某条待选清单' },
]
const FORMATS: ExportFormat[] = ['json', 'xlsx', 'md']

/** 导出材料包（09 屏左卡）。收集范围/格式/个人数据开关，回调导出。 */
export function ExportPanel({ filteredCount, selectedCount, shortlistCount, totalCount, exporting, onExport }: ExportPanelProps) {
  const [scope, setScope] = useState<ExportScope>('all')
  const [format, setFormat] = useState<ExportFormat>('json')
  const [work, setWork] = useState(false)

  const countText = (() => {
    if (scope === 'all') return totalCount ?? 0
    if (scope === 'filtered') return filteredCount ?? 0
    if (scope === 'selected') return selectedCount ?? 0
    return shortlistCount ?? 0
  })()

  const fileName = `MatSelect_材料包_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.${format === 'json' ? 'json' : format === 'xlsx' ? 'xlsx' : 'md'}`

  return (
    <div className="ms-card">
      <div className="ms-card__title">导出材料包</div>
      <div className="ms-col" style={{ gap: 'var(--sp-6)' }}>
        <div className="ms-data__section">
          <div className="ms-data__step-label">① 导出范围</div>
          <div className="ms-chips-edit">
            {SCOPES.map((s) => (
              <Chip
                key={s.value}
                size="26"
                selected={scope === s.value}
                onClick={() => setScope(s.value)}
              >
                {s.label}
                {s.value === 'all' ? `（${totalCount ?? 0}）` : s.value === 'filtered' ? `（${filteredCount ?? 0}）` : ''}
              </Chip>
            ))}
          </div>
        </div>

        <div className="ms-data__section">
          <div className="ms-data__step-label">② 导出格式</div>
          <div className="ms-chips-edit">
            {FORMATS.map((f) => (
              <Chip key={f} size="26" selected={format === f} onClick={() => setFormat(f)}>
                {f === 'json' ? 'JSON · 全字段，可再导入' : f === 'xlsx' ? 'Excel · 便于筛选排序' : 'Markdown · 贴进文档'}
              </Chip>
            ))}
          </div>
        </div>

        <div className="ms-info-block ms-row" style={{ justifyContent: 'space-between' }}>
          <div className="ms-col" style={{ gap: 2 }}>
            <span style={{ fontSize: 'var(--fs-caption)', color: 'var(--text-3)', lineHeight: 16 }}>
              包含我的工作数据（任务 / 待选备注 / 回评）
            </span>
            <span style={{ fontSize: 'var(--fs-caption)', color: 'var(--text-7)', lineHeight: 16 }}>
              默认关闭 —— 个人数据不外流，导入方看不到你的待选与回评
            </span>
          </div>
          <button
            className={`ms-switch${work ? ' ms-switch--on' : ''}`}
            role="switch"
            aria-checked={work}
            aria-label="包含个人数据"
            onClick={() => setWork((v) => !v)}
          >
            <span className="ms-switch__knob" />
          </button>
        </div>

        <div className="ms-info-block" aria-busy={exporting || undefined}>
          {exporting ? (
            <Skeleton height={14} width="72%" />
          ) : (
            <span className="ms-mono" style={{ fontSize: 'var(--fs-small)', color: 'var(--text-3)' }}>
              {fileName} · 约 {Math.max(1, Math.round((countText as number) * 8.2))} KB · {countText} 条材料 · 含校验和
            </span>
          )}
        </div>

        <div className="ms-row" style={{ justifyContent: 'flex-end' }}>
          <button className="ms-btn ms-btn--primary" disabled={exporting} onClick={() => onExport({ scope, format, include_work_data: work })}>
            {exporting && <span className="ms-spin" style={{ color: '#fff' }} />}
            导出材料包
          </button>
        </div>
      </div>
    </div>
  )
}

export default ExportPanel
