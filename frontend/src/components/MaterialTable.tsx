import { useNavigate } from 'react-router-dom'
import type { MaterialCard as MaterialCardT } from '../api/types'
import { Icon } from '../icons'
import { formatRange, formatPrice, formatTime } from '../utils/format'
import './ui.css'
import '../pages/pages.css'

export type MaterialSort = 'category_name' | 'density' | 'service_temp_limit' | 'price' | 'updated_at' | 'name'

/** 列表卡片类型未含 阻燃等级/更新日期（契约 MaterialCard 精简），本地按可选字段扩展。 */
type TableMat = MaterialCardT & {
  certifications?: { ul94?: string | null } | null
  updated_at?: string
}

export interface MaterialTableProps {
  materials: TableMat[]
  loading?: boolean
  selectable?: boolean
  selectedIds?: string[]
  onToggleSelect?: (uid: string) => void
  sort?: MaterialSort
  onSort?: (s: MaterialSort) => void
  onOpen?: (uid: string) => void
  onExportSelected?: () => void
}

const COLS = 9

export function MaterialTable({
  materials,
  loading,
  selectable,
  selectedIds = [],
  onToggleSelect,
  sort,
  onSort,
  onOpen,
  onExportSelected,
}: MaterialTableProps) {
  const navigate = useNavigate()
  const open = (uid: string) => (onOpen ? onOpen(uid) : navigate(`/materials/${uid}`))

  const head = (
    <thead>
      <tr>
        {selectable && (
          <th style={{ width: 40, padding: '0 8px', textAlign: 'center' }}>
            <input
              type="checkbox"
              aria-label="全选"
              checked={selectedIds.length > 0 && selectedIds.length === materials.length}
              ref={(el) => {
                if (el) el.indeterminate = selectedIds.length > 0 && selectedIds.length < materials.length
              }}
              onChange={() => {
                const allSelected = selectedIds.length === materials.length
                materials.forEach((m) => {
                  const isSel = selectedIds.includes(m.uid)
                  if (allSelected && isSel) onToggleSelect?.(m.uid)
                  if (!allSelected && !isSel) onToggleSelect?.(m.uid)
                })
              }}
            />
          </th>
        )}
        <th style={{ width: 230 }} onClick={() => onSort?.('name')}>材料名称{sort === 'name' ? ' ⌄' : ''}</th>
        <th style={{ width: 92 }} onClick={() => onSort?.('category_name')}>类别{sort === 'category_name' ? ' ⌄' : ''}</th>
        <th style={{ width: 92 }} className="is-mono" onClick={() => onSort?.('density')}>密度 g/cm³{sort === 'density' ? ' ⌄' : ''}</th>
        <th style={{ width: 108 }} className="is-mono" onClick={() => onSort?.('service_temp_limit')}>耐温上限 °C{sort === 'service_temp_limit' ? ' ⌄' : ''}</th>
        <th style={{ width: 108 }} className="is-mono" onClick={() => onSort?.('price')}>参考价 元/kg{sort === 'price' ? ' ⌄' : ''}</th>
        <th style={{ width: 80 }}>推荐工艺</th>
        <th style={{ width: 92 }} className="is-mono">阻燃等级</th>
        <th style={{ width: 100 }} className="is-mono" onClick={() => onSort?.('updated_at')}>更新日期{sort === 'updated_at' ? ' ⌄' : ''}</th>
        <th style={{ width: 134, textAlign: 'right' }}>操作</th>
      </tr>
    </thead>
  )

  if (loading) {
    return (
      <div className="ms-table-wrap">
        <table className="ms-table">
          {head}
          <tbody>
            {Array.from({ length: 12 }).map((_, i) => (
              <tr key={i}>
                {selectable && <td style={{ padding: '0 8px', textAlign: 'center' }}><div className="ms-skel" style={{ width: 14, height: 14, margin: '0 auto' }} /></td>}
                {Array.from({ length: COLS }).map((__, j) => (
                  <td key={j}><div className="ms-skel" style={{ height: 12, width: j === 0 ? '70%' : 60 }} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="ms-table-wrap">
      <table className="ms-table">
        {head}
        <tbody>
          {materials.map((m) => (
            <tr key={m.uid} className={selectedIds.includes(m.uid) ? 'is-selected' : ''}>
              {selectable && (
                <td style={{ padding: '0 8px', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    aria-label={`选择 ${m.name}`}
                    checked={selectedIds.includes(m.uid)}
                    onChange={() => onToggleSelect?.(m.uid)}
                  />
                </td>
              )}
              <td className="is-name" style={{ cursor: 'pointer' }} onClick={() => open(m.uid)}>
                {m.name}
              </td>
              <td>{m.category_name ?? '—'}</td>
              <td className="is-mono">{formatRange(m.density_min, m.density_max)}</td>
              <td className="is-mono">{m.service_temp_limit == null ? '—' : m.service_temp_limit}</td>
              <td className="is-mono">{formatPrice(m.price_min, m.price_max, m.price_unit)}</td>
              <td>{m.molding_process?.[0] ?? '—'}</td>
              <td className="is-mono">{m.certifications?.ul94 ?? '—'}</td>
              <td className="is-mono" style={{ color: 'var(--text-5)' }}>{formatTime(m.updated_at)}</td>
              <td>
                <div className="ms-row ms-gap-2" style={{ justifyContent: 'flex-end' }}>
                  <button className="ms-icon-btn" aria-label="编辑材料" title="编辑材料" onClick={() => navigate(`/materials/${m.uid}/edit`)}>
                    <Icon name="edit" size={14} />
                  </button>
                  <button className="ms-icon-btn" aria-label="查看变更历史" title="查看变更历史" onClick={() => navigate(`/materials/${m.uid}/history`)}>
                    <Icon name="clock" size={14} />
                  </button>
                  <button className="ms-icon-btn" aria-label="更多" title="更多" onClick={() => open(m.uid)}>
                    <Icon name="more" size={14} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div
        style={{
          height: 44,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 12px',
          fontSize: 'var(--fs-small)',
          color: 'var(--text-6)',
          borderTop: '1px solid var(--border-row)',
        }}
      >
        <span>已显示 {materials.length} 条 · 滚动到底部自动加载更多</span>
        {selectable && selectedIds.length > 0 && (
          <button className="ms-link" onClick={onExportSelected}>
            导出选中行为 Excel
          </button>
        )}
      </div>
    </div>
  )
}

export default MaterialTable
