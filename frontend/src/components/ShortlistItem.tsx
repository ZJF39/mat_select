import { useEffect, useRef, useState } from 'react'
import type { ShortlistItem as ShortlistItemT, ShortlistTag } from '../api/types'
import { Chip } from './Chip'
import { Icon } from '../icons'
import { TAG_LABEL, TAG_TONE } from '../utils/format'
import './ui.css'

const TAGS: ShortlistTag[] = ['key', 'pending', 'rejected']

export interface ShortlistItemProps {
  item: ShortlistItemT
  index: number
  total: number
  dragging: boolean
  grabbed: boolean
  newItem?: boolean
  onDragStart: () => void
  onDragOver: (e: React.DragEvent) => void
  onDrop: () => void
  onDragEnd: () => void
  onGripKeyDown: (e: React.KeyboardEvent) => void
  onRemove: () => void
  onNoteChange: (note: string) => void
  onTagChange: (tag: ShortlistTag) => void
}

/** 待选清单项（原型 03 §5.6 / 02 §04）：手柄 + 名 + 匹配度 + 参数 + 标记 + 备注（自动保存）。 */
export function ShortlistItem({
  item,
  index,
  total,
  dragging,
  grabbed,
  newItem,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  onGripKeyDown,
  onRemove,
  onNoteChange,
  onTagChange,
}: ShortlistItemProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(item.user_note)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (editing) ref.current?.focus()
  }, [editing])

  const save = () => {
    setEditing(false)
    if (draft !== item.user_note) onNoteChange(draft)
  }

  return (
    <div
      className={`ms-shortlist-item${newItem ? ' ms-shortlist-item--new' : ''}${dragging ? ' ms-dragging' : ''}`}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
      aria-roledescription="待选材料项"
    >
      <div className="ms-shortlist-item__top">
        <span
          className="ms-grip"
          role="button"
          tabIndex={0}
          aria-label={`调整顺序，当前第 ${index + 1} 位，共 ${total} 位${grabbed ? '（已提起，用上下键移动）' : ''}`}
          aria-pressed={grabbed}
          draggable
          onDragStart={onDragStart}
          onKeyDown={onGripKeyDown}
          onClick={() => ref.current?.focus()}
        >
          <Icon name="grip" size={12} />
        </span>
        <span className="ms-shortlist-item__name ms-ellipsis">{item.material.name}</span>
        <span className="ms-shortlist-item__score">{item.score}%</span>
      </div>

      <div className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>
        {item.material.molding_process?.[0] ?? '—'}
        {item.material.service_temp_limit != null ? ` · 耐温 ${item.material.service_temp_limit}°C` : ''}
      </div>

      <div className="ms-row ms-gap-3 ms-wrap">
        {TAGS.map((t) => (
          <Chip
            key={t}
            size="20"
            tone={item.tag === t ? (t === 'rejected' ? 'danger' : t === 'pending' ? 'warning' : 'accent') : 'default'}
            selected={item.tag === t}
            onClick={() => onTagChange(t)}
          >
            {TAG_LABEL[t]}
          </Chip>
        ))}
        <button className="ms-link" style={{ marginLeft: 'auto', background: 'none', border: 'none', fontSize: 'var(--fs-caption)' }} onClick={onRemove}>
          移出待选
        </button>
      </div>

      <div
        ref={ref}
        className="ms-shortlist-item__note"
        contentEditable={editing}
        suppressContentEditableWarning
        role="textbox"
        aria-label={`备注（${item.material.name}）`}
        onDoubleClick={() => setEditing(true)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            save()
          }
        }}
        onClick={() => !editing && setEditing(true)}
      >
        {item.user_note || '点击添加备注…'}
      </div>
    </div>
  )
}

export default ShortlistItem
