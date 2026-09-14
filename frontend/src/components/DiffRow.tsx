import type { DiffRow as DiffRowT } from '../api/types'
import './ui.css'

const TYPE_BADGE: Record<DiffRowT['type'], { cls: string; label: string }> = {
  add: { cls: 'ms-chip--success', label: '新增' },
  remove: { cls: 'ms-chip--danger', label: '删除' },
  modify: { cls: 'ms-chip--warning', label: '修改' },
}

export interface DiffRowProps {
  row: DiffRowT
}

/** diff 行（原型 03 §5.4 / 02 §08）：字段 / 变更前 / 箭头 / 变更后 / 类型徽章；三色；数组字段 Chip 级 diff。 */
export function DiffRow({ row }: DiffRowProps) {
  const badge = TYPE_BADGE[row.type]
  const isArray = row.before_items.length > 0 || row.after_items.length > 0

  const beforeNode = isArray ? (
    row.before_items.map((it, i) => (
      <span key={i} className={`ms-diff-chip${row.type === 'modify' ? ' ms-diff-chip--modify' : row.type === 'remove' ? ' ms-diff-chip--remove' : ''}`}>
        {it}
      </span>
    ))
  ) : (
    <span>{row.before ?? '—'}</span>
  )

  const afterNode = isArray ? (
    row.after_items.map((it, i) => (
      <span key={i} className={`ms-diff-chip${row.type === 'modify' ? ' ms-diff-chip--modify' : row.type === 'add' ? ' ms-diff-chip--add' : ''}`}>
        {it}
      </span>
    ))
  ) : (
    <span>{row.after ?? '—'}</span>
  )

  return (
    <div className={`ms-diff-row ms-diff-row--${row.type}`}>
      <div className="ms-diff-row__field">{row.field}</div>
      <div className="ms-diff-row__cell ms-diff-row__cell--before">{beforeNode}</div>
      <div className="ms-diff-row__arrow">
        <span style={{ fontSize: 14, color: 'var(--text-8)' }}>→</span>
      </div>
      <div className="ms-diff-row__cell ms-diff-row__cell--after">{afterNode}</div>
      <div className="ms-diff-row__badge">
        <span className={`ms-chip ms-chip--24 ${badge.cls}`}>{badge.label}</span>
      </div>
    </div>
  )
}

export default DiffRow
