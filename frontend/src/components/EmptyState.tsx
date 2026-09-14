import type { ReactNode } from 'react'
import { Icon, type IconName } from '../icons'
import './ui.css'

export interface EmptyStateProps {
  icon?: IconName
  title: string
  desc?: string
  action?: ReactNode
  compact?: boolean
}

/** 空态（原型 05 §2）：说明「为什么空」+「下一步做什么」+ 可选动作。 */
export function EmptyState({ icon = 'layers', title, desc, action, compact }: EmptyStateProps) {
  return (
    <div className={`ms-empty${compact ? '' : ''}`} style={compact ? { padding: 'var(--sp-10) var(--sp-8)' } : undefined}>
      <span className="ms-empty__icon">
        <Icon name={icon} size={28} />
      </span>
      <div className="ms-empty__title">{title}</div>
      {desc && <div className="ms-empty__desc">{desc}</div>}
      {action && <div style={{ marginTop: 'var(--sp-4)' }}>{action}</div>}
    </div>
  )
}

export default EmptyState
