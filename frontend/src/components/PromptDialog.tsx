import { useEffect, useState } from 'react'
import { Modal } from './Modal'
import './ui.css'

export interface PromptDialogProps {
  open: boolean
  title: string
  /** 输入项标签（如「分类名称」） */
  label?: string
  defaultValue?: string
  placeholder?: string
  confirmText?: string
  /** 返回错误文案则阻止提交并就地提示；返回 null 表示通过 */
  validate?: (value: string) => string | null
  pending?: boolean
  onCancel: () => void
  onSubmit: (value: string) => void
}

/**
 * 文本输入对话框（原型 03 §3.7）。
 *
 * 用于替代 `window.prompt`：原生弹窗阻塞主线程、无法定制样式与校验、不遵循
 * 本项目的设计令牌，且移动端表现不可控。Enter 提交 / Esc 取消由 Modal 统一处理。
 */
export function PromptDialog({
  open,
  title,
  label,
  defaultValue = '',
  placeholder,
  confirmText = '确定',
  validate,
  pending,
  onCancel,
  onSubmit,
}: PromptDialogProps) {
  const [value, setValue] = useState(defaultValue)
  const [error, setError] = useState<string | null>(null)

  // 每次打开都以最新的初始值重置，避免沿用上一次输入的残留
  useEffect(() => {
    if (open) {
      setValue(defaultValue)
      setError(null)
    }
  }, [open, defaultValue])

  const submit = () => {
    const msg = validate?.(value) ?? null
    if (msg) {
      setError(msg)
      return
    }
    setError(null)
    onSubmit(value)
  }

  return (
    <Modal
      open={open}
      title={title}
      width={420}
      onClose={onCancel}
      footer={
        <>
          <span className="ms-field__err">{error}</span>
          <div className="ms-row ms-gap-3">
            <button className="ms-btn ms-btn--ghost" onClick={onCancel}>
              取消
            </button>
            <button className="ms-btn ms-btn--primary" onClick={submit} disabled={pending}>
              {confirmText}
            </button>
          </div>
        </>
      }
    >
      <label className="ms-field">
        {label && <span className="ms-field__label">{label}</span>}
        <input
          className={`ms-input${error ? ' ms-input--error' : ''}`}
          autoFocus
          aria-label={label ?? title}
          placeholder={placeholder}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            if (error) setError(null)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              submit()
            }
          }}
        />
      </label>
    </Modal>
  )
}

export default PromptDialog
