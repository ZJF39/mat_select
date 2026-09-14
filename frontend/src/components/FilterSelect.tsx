import { useEffect, useRef, useState } from 'react'
import { Icon } from '../icons'
import './ui.css'

export interface FilterOption {
  value: string
  label: string
  count?: number
}

export interface RangeValue {
  min?: number
  max?: number
}

interface BaseProps {
  label: string
  active?: boolean
  display?: string
}

interface MultiProps extends BaseProps {
  mode: 'multi'
  options: FilterOption[]
  value: string[]
  onChange: (v: string[]) => void
}

interface RangeProps extends BaseProps {
  mode: 'range'
  value: RangeValue
  onChange: (v: RangeValue) => void
  unit?: string
}

interface SingleProps extends BaseProps {
  mode: 'single'
  options: FilterOption[]
  value: string[]
  onChange: (v: string[]) => void
}

type FilterSelectProps = MultiProps | RangeProps | SingleProps

function useClickOutside(ref: React.RefObject<HTMLElement>, onClose: () => void) {
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [ref, onClose])
}

/** 筛选项（原型 03 §6.1）：Popover，多选/区间，即时生效（无查询按钮）。 */
export function FilterSelect(props: FilterSelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useClickOutside(ref, () => setOpen(false))

  const { label, active, display } = props
  const triggerLabel = display ?? label

  const close = () => setOpen(false)

  return (
    <div style={{ position: 'relative' }} ref={ref}>
      <button
        type="button"
        className={`ms-filter${active ? ' ms-filter--active' : ''}`}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {active ? <span className="ms-filter__val">{triggerLabel}</span> : <span>{label}</span>}
        <span className="ms-filter__caret">
          <Icon name="chevronDown" size={10} />
        </span>
      </button>

      {open && (
        <div className="ms-filter-pop" role="dialog" aria-label={label}>
          {props.mode === 'range' ? (
            <RangeBody value={props.value} unit={props.unit} onChange={props.onChange} onClose={close} />
          ) : (
            <MultiBody
              options={props.options}
              value={props.value}
              onChange={props.onChange}
              onClose={close}
            />
          )}
        </div>
      )}
    </div>
  )
}

function MultiBody({
  options,
  value,
  onChange,
  onClose,
}: {
  options: FilterOption[]
  value: string[]
  onChange: (v: string[]) => void
  onClose: () => void
}) {
  const toggle = (v: string) => {
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v])
  }
  return (
    <>
      <div className="ms-filter-pop__title">选择（即时生效）</div>
      <div className="ms-filter-pop__checks">
        {options.map((o) => (
          <label key={o.value} className="ms-filter-check">
            <input type="checkbox" checked={value.includes(o.value)} onChange={() => toggle(o.value)} />
            <span className="ms-ellipsis">{o.label}</span>
            {o.count != null && <span className="ms-tree-row__count" style={{ marginLeft: 'auto' }}>{o.count}</span>}
          </label>
        ))}
        {options.length === 0 && <div className="ms-muted" style={{ fontSize: 'var(--fs-small)' }}>暂无可选项</div>}
      </div>
      <div className="ms-filter-pop__foot">
        <button className="ms-btn ms-btn--sm ms-btn--ghost" onClick={() => onChange([])}>
          重置
        </button>
        <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={onClose}>
          应用
        </button>
      </div>
    </>
  )
}

function RangeBody({
  value,
  unit,
  onChange,
  onClose,
}: {
  value: RangeValue
  unit?: string
  onChange: (v: RangeValue) => void
  onClose: () => void
}) {
  return (
    <>
      <div className="ms-filter-pop__title">区间（即时生效）</div>
      <div className="ms-range-wrap">
        <input
          className="ms-input ms-input--mono"
          type="number"
          placeholder="最小"
          aria-label="最小"
          value={value.min ?? ''}
          onChange={(e) => onChange({ ...value, min: e.target.value === '' ? undefined : Number(e.target.value) })}
        />
        <span className="ms-range-sep">–</span>
        <input
          className="ms-input ms-input--mono"
          type="number"
          placeholder="最大"
          aria-label="最大"
          value={value.max ?? ''}
          onChange={(e) => onChange({ ...value, max: e.target.value === '' ? undefined : Number(e.target.value) })}
        />
        {unit && <span className="ms-muted" style={{ fontSize: 'var(--fs-small)' }}>{unit}</span>}
      </div>
      <div className="ms-filter-pop__foot">
        <button className="ms-btn ms-btn--sm ms-btn--ghost" onClick={() => onChange({})}>
          重置
        </button>
        <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={onClose}>
          应用
        </button>
      </div>
    </>
  )
}

export default FilterSelect
