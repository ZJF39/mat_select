import { useState, type ReactNode } from 'react'
import './ui.css'

export interface TooltipProps {
  content: ReactNode
  children: ReactNode
}

/** 轻量 hover/focus 提示（原型 04 分数拆解条维度解释）。 */
export function Tooltip({ content, children }: TooltipProps) {
  const [show, setShow] = useState(false)
  return (
    <span
      className="ms-tip"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      tabIndex={0}
    >
      {children}
      {show && <span className="ms-tip__pop" role="tooltip">{content}</span>}
    </span>
  )
}

export default Tooltip
