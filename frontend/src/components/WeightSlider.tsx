import { useRef } from 'react'
import './ui.css'

export interface WeightSliderProps {
  label: string
  hint?: string
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  disabled?: boolean
}

/**
 * 权重滑杆（原型 03 §6.3 / 02 §10）
 * 键盘：←/→ 步进 1；Shift+←/→ 步进 5；Home/End 到边界；aria-valuenow 为数字。
 */
export function WeightSlider({ label, hint, value, onChange, min = 0, max = 100, disabled }: WeightSliderProps) {
  const ref = useRef<HTMLInputElement>(null)

  const clamp = (v: number) => Math.max(min, Math.min(max, v))

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    let next: number | null = null
    const step = e.shiftKey ? 5 : 1
    if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') next = clamp(value - step)
    else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') next = clamp(value + step)
    else if (e.key === 'Home') next = min
    else if (e.key === 'End') next = max
    if (next !== null) {
      e.preventDefault()
      onChange(next)
    }
  }

  const pct = ((value - min) / (max - min)) * 100

  return (
    <div className="ms-wslider">
      <div className="ms-wslider__top">
        <div>
          <div className="ms-wslider__label">{label}</div>
          {hint && <div className="ms-wslider__hint">{hint}</div>}
        </div>
        <span className="ms-wslider__val">{value}%</span>
      </div>
      <div className="ms-wslider__fill" style={{ ['--fill' as string]: `${pct}%` }}>
        <input
          ref={ref}
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          disabled={disabled}
          aria-label={label}
          aria-valuenow={value}
          aria-valuemin={min}
          aria-valuemax={max}
          onChange={(e) => onChange(Number(e.target.value))}
          onKeyDown={onKeyDown}
          style={{ ['--fill' as string]: `${pct}%` } as React.CSSProperties}
        />
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: 0,
            top: '50%',
            transform: 'translateY(-50%)',
            width: `${pct}%`,
            height: 8,
            borderRadius: 'var(--radius-xs)',
            background: 'var(--color-accent)',
            pointerEvents: 'none',
          }}
        />
      </div>
    </div>
  )
}

export default WeightSlider
