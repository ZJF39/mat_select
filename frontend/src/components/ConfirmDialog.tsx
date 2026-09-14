import type { ReactNode } from 'react'
import { Modal } from './Modal'
import './ui.css'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  children: ReactNode
  confirmText?: string
  cancelText?: string
  /** danger 用于不可逆 / 破坏性操作（原型 02 §11、05 §1.2） */
  tone?: 'primary' | 'danger'
  pending?: boolean
  /** 底部左侧补充说明，例如「此操作不可撤销」 */
  note?: ReactNode
  onCancel: () => void
  onConfirm: () => void
}

/**
 * 二次确认对话框（原型 02 §11 / 05 §1.2）。
 *
 * 约定：破坏性操作必须二次确认并明示后果（数据是否可恢复、影响范围）；
 * 使用全站统一的 `ms-modal`，不使用 `window.confirm`。
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmText = '确认',
  cancelText = '取消',
  tone = 'primary',
  pending,
  note,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      title={title}
      width={420}
      onClose={onCancel}
      footer={
        <>
          <span className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>
            {note}
          </span>
          <div className="ms-row ms-gap-3">
            <button className="ms-btn ms-btn--ghost" onClick={onCancel}>
              {cancelText}
            </button>
            <button
              className={`ms-btn ms-btn--${tone === 'danger' ? 'danger' : 'primary'}`}
              onClick={onConfirm}
              disabled={pending}
            >
              {confirmText}
            </button>
          </div>
        </>
      }
    >
      {children}
    </Modal>
  )
}

export default ConfirmDialog
