import type { ReactNode } from 'react'
import { Icon } from '../icons'
import './ui.css'

type Tone = 'default' | 'accent' | 'success' | 'warning' | 'danger' | 'info'

const TONE_CLASS: Record<Tone, string> = {
  default: '',
  accent: 'ms-chip--accent',
  success: 'ms-chip--success',
  warning: 'ms-chip--warning',
  danger: 'ms-chip--danger',
  info: 'ms-chip--info',
}

const SIZE_CLASS: Record<'20' | '24' | '26' | '30', string> = {
  '20': '',
  '24': 'ms-chip--24',
  '26': 'ms-chip--26',
  '30': 'ms-chip--30',
}

export interface ChipProps {
  children: ReactNode
  tone?: Tone
  size?: '20' | '24' | '26' | '30'
  selected?: boolean
  closable?: boolean
  onClose?: (e: React.MouseEvent) => void
  onClick?: (e: React.MouseEvent) => void
  className?: string
  title?: string
  /** 供不可见语义补全（如纯数字标签的「匹配度」前缀） */
  ariaLabel?: string
}

/** 标签 Chip（原型 03 §3.1）：底 bg-sunken；选中/语义变体；可关闭。 */
export function Chip({
  children,
  tone = 'default',
  size = '20',
  selected,
  closable,
  onClose,
  onClick,
  className = '',
  title,
  ariaLabel,
}: ChipProps) {
  const cls = [
    'ms-chip',
    TONE_CLASS[tone],
    SIZE_CLASS[size],
    selected ? 'ms-chip--selected' : '',
    onClick ? 'ms-chip--selectable' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  const content = (
    <>
      <span className="ms-ellipsis">{children}</span>
      {closable && (
        <span
          className="ms-chip__close"
          role="button"
          aria-label="移除"
          onClick={(e) => {
            e.stopPropagation()
            onClose?.(e)
          }}
        >
          <Icon name="close" size={10} />
        </span>
      )}
    </>
  )

  if (onClick) {
    return (
      <button type="button" className={cls} onClick={onClick} title={title} aria-label={ariaLabel} aria-pressed={selected}>
        {content}
      </button>
    )
  }
  return (
    <span className={cls} title={title} aria-label={ariaLabel}>
      {content}
    </span>
  )
}

export default Chip
