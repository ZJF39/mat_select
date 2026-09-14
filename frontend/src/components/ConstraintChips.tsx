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

type EditableKey = 'part_type' | 'process' | 'temp_limit'

const EDIT_LABEL: Record<EditableKey, string> = {
  part_type: '零件类型',
  process: '工艺',
  temp_limit: '温度上限（°C）',
}

/**
 * 约束标签（原型 02 §04 / 03 §3.12）：可编辑标签 + `+ 添加约束`。
 *
 * 点击标签文字**就地进入编辑**（只改值、不新增），复用本组件 `+ 添加约束`
 * 的行内输入形态：Enter 提交、Esc 取消、失焦提交。
 *
 * 原实现用 `window.prompt` 取新值，与全站自定义弹窗交互不一致，样式不受设计
 * 令牌控制，且无法对温度做即时校验（输入非数字会被 `Number()` 静默转成 NaN）。
 */
export function ConstraintChips({ constraints, onRemove, onChange, onAdd }: ConstraintChipsProps) {
  const [adding, setAdding] = useState(false)
  const [field, setField] = useState<EditableKey>('part_type')
  const [val, setVal] = useState('')
  const [editing, setEditing] = useState<{ key: EditableKey; val: string } | null>(null)

  const chips: { key: keyof Constraints | 'extra'; label: string }[] = []
  if (constraints.part_type) chips.push({ key: 'part_type', label: `零件类型 · ${constraints.part_type}` })
  if (constraints.process) chips.push({ key: 'process', label: `工艺 · ${constraints.process}` })
  if (constraints.temp_limit != null) chips.push({ key: 'temp_limit', label: `温度 ≤ ${constraints.temp_limit} °C` })
  constraints.extra.forEach((e) => chips.push({ key: 'extra', label: e }))

  const submitAdd = () => {
    if (!val.trim()) return
    onAdd(field, field === 'temp_limit' ? Number(val) : val)
    setVal('')
    setAdding(false)
  }

  const startEdit = (key: keyof Constraints | 'extra') => {
    // extra 为自由文本标签，只支持移除，不支持就地改值（保留原有能力边界）
    if (key === 'extra') return
    setEditing({ key, val: String(constraints[key] ?? '') })
  }

  const submitEdit = () => {
    if (!editing) return
    const { key, val: raw } = editing
    const text = raw.trim()
    if (key === 'temp_limit') {
      const n = Number(text)
      // 空值或非数字视为放弃修改，不写回 NaN
      if (text !== '' && !Number.isNaN(n)) onChange('temp_limit', n)
    } else if (text !== '') {
      onChange(key, text)
    }
    setEditing(null)
  }

  return (
    <div className="ms-constraints__row">
      {chips.map((c) => {
        // editing.key 的取值域已排除 'extra'，故此处无需再判 c.key !== 'extra'
        if (editing && c.key === editing.key) {
          const key = c.key as EditableKey
          return (
            <span key={`${c.key}-edit`} className="ms-row ms-gap-3" style={{ height: 28 }}>
              <input
                className="ms-input ms-input--mono"
                style={{ height: 28, width: 120 }}
                autoFocus
                aria-label={`修改${EDIT_LABEL[key]}`}
                placeholder={EDIT_LABEL[key]}
                value={editing.val}
                onChange={(e) => setEditing({ key, val: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    submitEdit()
                  }
                  if (e.key === 'Escape') {
                    e.stopPropagation()
                    setEditing(null)
                  }
                }}
                onBlur={submitEdit}
              />
              <button
                className="ms-btn ms-btn--sm ms-btn--secondary"
                // 防止按下按钮时输入框先失焦、导致提交两次
                onMouseDown={(e) => e.preventDefault()}
                onClick={submitEdit}
              >
                确定
              </button>
            </span>
          )
        }
        return (
          <span
            key={`${c.key}-${c.label}`}
            className="ms-chip ms-chip--26"
            style={{ height: 28, borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-control)', background: 'var(--bg-surface)', cursor: 'pointer' }}
            title={c.key === 'extra' ? '× 移除' : '点击编辑，× 移除'}
          >
            <span className="ms-ellipsis" onClick={() => startEdit(c.key)}>
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
        )
      })}

      {adding ? (
        <span className="ms-row ms-gap-3" style={{ height: 28 }}>
          <select
            className="ms-input"
            style={{ height: 28, width: 'auto' }}
            value={field}
            onChange={(e) => setField(e.target.value as typeof field)}
          >
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
