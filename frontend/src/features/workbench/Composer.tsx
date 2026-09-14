import { useRef, useState } from 'react'
import './ui.css'
import '../../pages/pages.css'

export interface ComposerProps {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

/** 输入区（原型 02 §04）：Enter 发送 / Shift+Enter 换行；底部提示 + 发送主按钮。 */
export function Composer({ onSend, disabled, placeholder }: ComposerProps) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  const autoSize = () => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  const send = () => {
    const v = text.trim()
    if (!v || disabled) return
    onSend(v)
    setText('')
    if (ref.current) ref.current.style.height = 'auto'
  }

  return (
    <div className="ms-wb__composer">
      <div className="ms-composer__box">
        <textarea
          ref={ref}
          className="ms-composer__input"
          value={text}
          disabled={disabled}
          placeholder={placeholder ?? '描述你的选材需求，例如「保险丝座，耐温 150°C，注塑」'}
          aria-label="选材需求输入"
          onChange={(e) => {
            setText(e.target.value)
            autoSize()
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
        />
        <div className="ms-composer__foot">
          <span className="ms-composer__hint">Enter 发送 · Shift + Enter 换行 · 追问会沿用本任务上下文</span>
          <button className="ms-btn ms-btn--primary" disabled={disabled || !text.trim()} onClick={send}>
            发送
          </button>
        </div>
      </div>
    </div>
  )
}

export default Composer
