import { useEffect, useRef, type ReactNode } from 'react'
import { Icon } from '../icons'
import './ui.css'

export interface ModalProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  width?: number
  /** 触发按钮，用于关闭后焦点回归 */
  triggerRef?: React.RefObject<HTMLElement>
}

/**
 * 轻量 Modal（仅 Modal 有投影，02 §11 + 05 §3）。
 * Esc 关闭；打开后焦点移入弹窗；关闭后焦点回到触发按钮。
 */
export function Modal({ open, title, onClose, children, footer, width = 560, triggerRef }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    // 焦点移入弹窗
    const t = window.setTimeout(() => {
      const focusable = panelRef.current?.querySelector<HTMLElement>(
        'input, textarea, button, select, [tabindex]',
      )
      focusable?.focus()
    }, 0)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.clearTimeout(t)
      triggerRef?.current?.focus()
    }
  }, [open, onClose, triggerRef])

  if (!open) return null

  return (
    <div className="ms-modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className="ms-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={panelRef}
        style={{ width }}
      >
        <div className="ms-modal__head">
          <span className="ms-modal__title">{title}</span>
          <button className="ms-icon-btn" aria-label="关闭" onClick={onClose}>
            <Icon name="close" size={16} />
          </button>
        </div>
        <div className="ms-modal__body">{children}</div>
        {footer && <div className="ms-modal__foot">{footer}</div>}
      </div>
    </div>
  )
}

export default Modal
