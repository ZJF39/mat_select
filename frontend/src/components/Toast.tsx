import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Icon, type IconName } from '../icons'
import './ui.css'

type Tone = 'default' | 'success' | 'danger'
interface ToastItem {
  id: number
  text: string
  tone: Tone
}

let items: ToastItem[] = []
let seq = 0
const listeners = new Set<(items: ToastItem[]) => void>()

function emit() {
  listeners.forEach((l) => l([...items]))
}

/** 轻提示（成功反馈 / 错误回滚）。自动消失，不阻塞。 */
export function toast(text: string, tone: Tone = 'default', duration = 2400) {
  const id = ++seq
  items = [...items, { id, text, tone }]
  emit()
  window.setTimeout(() => {
    items = items.filter((i) => i.id !== id)
    emit()
  }, duration)
}

const ICON: Record<Tone, IconName> = { default: 'info', success: 'check', danger: 'danger' }

/** 单例挂载到 body；无需 Provider，可在任意页面渲染一次。 */
export function ToastHost() {
  const [, set] = useState<ToastItem[]>(items)
  useEffect(() => {
    const l = (next: ToastItem[]) => set(next)
    listeners.add(l)
    return () => {
      listeners.delete(l)
    }
  }, [])
  return createPortal(
    <div className="ms-toast-wrap" aria-live="polite">
      {items.map((it) => (
        <div key={it.id} className={`ms-toast ms-toast--${it.tone}`} role="status">
          <Icon name={ICON[it.tone]} size={14} />
          <span>{it.text}</span>
        </div>
      ))}
    </div>,
    document.body,
  )
}

export default ToastHost
