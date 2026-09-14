import { useState } from 'react'
import type { ShortlistItem, ShortlistTag } from '../api/types'
import { Icon } from '../icons'
import { Chip } from './Chip'
import { TAG_LABEL } from '../utils/format'
import { formatRange, formatPrice } from '../utils/format'
import './ui.css'

const TAG_CYCLE: ShortlistTag[] = ['key', 'pending', 'rejected']

export interface CompareRowProps {
  item: ShortlistItem
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
  onNoteChange: (note: string) => void
  onTagChange: (tag: ShortlistTag) => void
}

/** 对比表行（原型 03 §5.3 / 02 §05）：8 列 + 拖拽手柄 + 备注内联编辑。
 *  行首手柄同时支持鼠标拖拽与键盘（空格/回车提起 → ↑/↓ 移动 → Esc 取消）。 */
export function CompareRow({
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
  onNoteChange,
  onTagChange,
}: CompareRowProps) {
  const m = item.material
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(item.user_note)

  return (
    <tr
      className={item.tag === 'rejected' ? 'is-rejected' : ''}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
    >
      <td style={{ width: 24, padding: '0 4px' }}>
        <span
          className="ms-grip"
          role="button"
          tabIndex={0}
          aria-label={`调整顺序，当前第 ${index + 1} 位，共 ${total} 位${grabbed ? '（已提起，用上下键移动）' : ''}`}
          aria-pressed={grabbed}
          draggable
          onDragStart={onDragStart}
          onKeyDown={onGripKeyDown}
        >
          <Icon name="grip" size={12} />
        </span>
      </td>
      <td className="is-name ms-ellipsis" style={{ width: 180 }}>{m.name}</td>
      <td className="is-mono" style={{ width: 76 }} aria-label={`匹配度 ${item.score}%`}>{item.score}%</td>
      <td className="is-mono" style={{ width: 80 }}>{formatRange(m.density_min, m.density_max)}</td>
      <td className="is-mono" style={{ width: 110 }}>
        {m.tensile_strength_min == null && m.tensile_strength_max == null
          ? '—'
          : formatRange(m.tensile_strength_min, m.tensile_strength_max)}
      </td>
      <td className="is-mono" style={{ width: 96 }}>{m.service_temp_limit == null ? '—' : m.service_temp_limit}</td>
      <td className="is-mono" style={{ width: 104 }}>{formatPrice(m.price_min, m.price_max, m.price_unit)}</td>
      <td style={{ width: 100 }}>
        <Chip
          size="20"
          tone={item.tag === 'rejected' ? 'danger' : item.tag === 'pending' ? 'warning' : 'accent'}
          onClick={() => {
            const next = TAG_CYCLE[(TAG_CYCLE.indexOf(item.tag) + 1) % TAG_CYCLE.length]
            onTagChange(next)
          }}
          title="点击切换标记"
        >
          {TAG_LABEL[item.tag]}
        </Chip>
      </td>
      <td style={{ width: 290 }}>
        {editing ? (
          <textarea
            className="ms-compare__note"
            autoFocus
            value={draft}
            style={{ height: 32 }}
            onBlur={() => {
              setEditing(false)
              if (draft !== item.user_note) onNoteChange(draft)
            }}
            onChange={(e) => setDraft(e.target.value)}
          />
        ) : (
          <span
            className="ms-compare__note"
            title="点击编辑备注"
            onClick={() => setEditing(true)}
          >
            {item.user_note || '点击添加备注…'}
          </span>
        )}
      </td>
    </tr>
  )
}

export default CompareRow
