import { useState } from 'react'
import type { Constraints } from '../api/types'
import { Icon } from '../icons'
import './ui.css'

export interface ConstraintChipsProps {
  constraints: Constraints
  onRemove: (key: keyof Constraints | 'extra') => void
  onChange: (key: keyof Constraints, value: string | number | null) => void
  onAdd: (key: keyof Constraints, value: string | number) => void
}

/** 约束标签（原型 02 §04 / 03 §3.12）：可编辑标签 + `+ 添加约束`。 */
export function ConstraintChips({ constraints, onRemove, onChange, onAdd }: ConstraintChipsProps) {
  const [adding, setAdding] = useState(false)
  const [field, setField] = useState<'part_type' | 'process' | 'temp_limit'>('part_type')
  const [val, setVal] = useState('')

  const chips: { key: keyof Constraints | 'extra'; label: string }[] = []
  if (constraints.part_type) chips.push({ key: 'part_type', label: `零件类型 · ${constraints.part_type}` })
  if (constraints.process) chips.push({ key: 'process', label: `工艺 · ${constraints.process}` })
  if (constraints.temp_limit != null) chips.push({ key: 'temp_limit', label: `温度 ≤ ${constraints.temp_limit} °C` })
  constraints.extra.forEach((e, i) => chips.push({ key: 'extra', label: e }))

  const submitAdd = () => {
    if (!val.trim()) return
    onAdd(field, field === 'temp_limit' ? Number(val) : val)
    setVal('')
    setAdding(false)
  }

  return (
    <div className="ms-constraints__row">
      {chips.map((c) => (
        <span key={`${c.key}-${c.label}`} className="ms-chip ms-chip--26" style={{ height: 28, borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-control)', background: 'var(--bg-surface)', cursor: 'pointer' }} title="点击编辑，× 移除">
          <span
            className="ms-ellipsis"
            onClick={() => {
              if (c.key === 'temp_limit') {
                const nv = window.prompt('修改温度上限（°C）', String(constraints.temp_limit ?? ''))
                if (nv != null && nv.trim() !== '') onChange('temp_limit', Number(nv))
              } else if (c.key !== 'extra') {
                const nv = window.prompt('修改约束值', String(constraints[c.key] ?? ''))
                if (nv != null) onChange(c.key, nv)
              }
            }}
          >
            {c.label}
          </span>
          <span
            className="ms-chip__close"
            role="button"
            aria-label="移除约束"
            onClick={(e) => {
              e.stopPropagation()
              onRemove(c.key)
            }}
          >
            <Icon name="close" size={10} />
          </span>
        </span>
      ))}

      {adding ? (
        <span className="ms-row ms-gap-3" style={{ height: 28 }}>
          <select className="ms-input" style={{ height: 28, width: 'auto' }} value={field} onChange={(e) => setField(e.target.value as typeof field)}>
            <option value="part_type">零件类型</option>
            <option value="process">工艺</option>
            <option value="temp_limit">温度</option>
          </select>
          <input
            className="ms-input ms-input--mono"
            style={{ height: 28, width: 90 }}
            autoFocus
            placeholder={field === 'temp_limit' ? '°C' : '值'}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submitAdd()}
          />
          <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={submitAdd}>确定</button>
        </span>
      ) : (
        <button className="ms-link" style={{ background: 'none', border: 'none', fontSize: 'var(--fs-small)', fontWeight: 'var(--fw-medium)' }} onClick={() => setAdding(true)}>
          + 添加约束
        </button>
      )}
    </div>
  )
}

export default ConstraintChips
