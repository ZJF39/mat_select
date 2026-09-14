import type { ReactNode } from 'react'
import { Icon, type IconName } from '../icons'
import './ui.css'

type Tone = 'warning' | 'info' | 'danger' | 'success'

const ICON: Record<Tone, IconName> = {
  warning: 'alert',
  info: 'info',
  danger: 'danger',
  success: 'check',
}

const TONE_CLASS: Record<Tone, string> = {
  warning: 'ms-notice--warning',
  info: 'ms-notice--info',
  danger: 'ms-notice--danger',
  success: 'ms-notice--success',
}

export interface NoticeProps {
  tone: Tone
  children: ReactNode
  icon?: IconName
  className?: string
}

/** 提示条（原型 03 §3.3）：圆角 8 / 内边距 10 / 左图标 + 右文案。 */
export function Notice({ tone, children, icon, className = '' }: NoticeProps) {
  return (
    <div className={`ms-notice ${TONE_CLASS[tone]} ${className}`} role="note">
      <span className="ms-notice__icon">
        <Icon name={icon ?? ICON[tone]} size={14} />
      </span>
      <div className="ms-notice__body">{children}</div>
    </div>
  )
}

export default Notice
