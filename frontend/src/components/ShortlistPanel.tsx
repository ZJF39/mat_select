import { useEffect, useRef, useState } from 'react'
import type { ShortlistItem as ShortlistItemT, ShortlistTag } from '../api/types'
import { ShortlistItem } from './ShortlistItem'
import { Chip } from './Chip'
import { EmptyState } from './EmptyState'
import { Skeleton } from './Skeleton'
import { Icon } from '../icons'
import './ui.css'

export interface ShortlistPanelProps {
  items: ShortlistItemT[]
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  newIds?: number[]
  onReorder: (ids: number[]) => void
  onRemove: (id: number) => void
  onNoteChange: (id: number, note: string) => void
  onTagChange: (id: number, tag: ShortlistTag) => void
  onExport: () => void
}

/** 待选面板（原型 02 §04）：300px 右栏 + 拖拽排序 + 备注自动保存 + 导出对比表。 */
export function ShortlistPanel({
  items,
  loading,
  error,
  onRetry,
  newIds = [],
  onReorder,
  onRemove,
  onNoteChange,
  onTagChange,
  onExport,
}: ShortlistPanelProps) {
  const [orderIds, setOrderIds] = useState<number[]>(() => items.map((i) => i.id))
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [grabIndex, setGrabIndex] = useState<number | null>(null)
  const [announce, setAnnounce] = useState('')
  const liveRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setOrderIds((prev) => {
      const present = new Set(items.map((i) => i.id))
      const kept = prev.filter((id) => present.has(id))
      const added = items.map((i) => i.id).filter((id) => !kept.includes(id))
      return [...kept, ...added]
    })
  }, [items])

  const ordered = orderIds
    .map((id) => items.find((i) => i.id === id))
    .filter((x): x is ShortlistItemT => Boolean(x))

  const move = (from: number, to: number) => {
    if (from === to || from < 0 || to < 0 || from >= ordered.length || to >= ordered.length) return
    const next = [...orderIds]
    const [id] = next.splice(from, 1)
    next.splice(to, 0, id)
    setOrderIds(next)
    onReorder(next)
  }

  const onGripKeyDown = (index: number) => (e: React.KeyboardEvent) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault()
      setGrabIndex((g) => (g === index ? null : index))
      setAnnounce(grabIndex === index ? `已放下 ${ordered[index].material.name}` : `已提起 ${ordered[index].material.name}，用上下键移动`)
    } else if (grabIndex === index && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      e.preventDefault()
      const to = e.key === 'ArrowUp' ? index - 1 : index + 1
      move(index, to)
      setGrabIndex(to)
      setAnnounce(`已移动到第 ${to + 1} 位`)
    } else if (grabIndex === index && e.key === 'Escape') {
      setGrabIndex(null)
      setAnnounce('已取消调整')
    }
  }

  return (
    <aside className="ms-wb__panel" aria-label="待选材料面板">
      <div className="ms-wb__panel-head">
        <span className="ms-page-header__title" style={{ fontSize: 'var(--fs-body)' }}>待选材料</span>
        <Chip size="20" tone="accent">{ordered.length}</Chip>
        <button className="ms-link" style={{ marginLeft: 'auto', background: 'none', border: 'none', fontSize: 'var(--fs-small)' }} onClick={onExport}>
          导出对比表
        </button>
      </div>

      <div className="ms-wb__panel-body">
        <div className="sr-only" aria-live="polite" ref={liveRef} style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
          {announce}
        </div>
        {error ? (
          <div className="ms-notice ms-notice--danger" role="alert">
            <span className="ms-notice__icon"><Icon name="danger" size={14} /></span>
            <div className="ms-notice__body">
              {error}
              {onRetry && <button className="ms-link" style={{ background: 'none', border: 'none', display: 'block', marginTop: 4 }} onClick={onRetry}>重试</button>}
            </div>
          </div>
        ) : loading ? (
          <>
            <div className="ms-shortlist-item"><Skeleton height={16} width="60%" /><Skeleton height={12} width="80%" /></div>
            <div className="ms-shortlist-item"><Skeleton height={16} width="60%" /><Skeleton height={12} width="80%" /></div>
          </>
        ) : ordered.length === 0 ? (
          <EmptyState icon="plus" title="待选还是空的" desc="从上方推荐结果点击「+ 加入待选」，把感兴趣的材料收进来" compact />
        ) : (
          <div className="ms-shortlist">
            {ordered.map((it, i) => (
              <ShortlistItem
                key={it.id}
                item={it}
                index={i}
                total={ordered.length}
                dragging={dragIndex === i}
                grabbed={grabIndex === i}
                newItem={newIds.includes(it.id)}
                onDragStart={() => setDragIndex(i)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => {
                  if (dragIndex !== null) move(dragIndex, i)
                  setDragIndex(null)
                }}
                onDragEnd={() => setDragIndex(null)}
                onGripKeyDown={onGripKeyDown(i)}
                onRemove={() => onRemove(it.id)}
                onNoteChange={(note) => onNoteChange(it.id, note)}
                onTagChange={(tag) => onTagChange(it.id, tag)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="ms-wb__panel-foot">
        拖拽卡片可调整重视度顺序；备注会自动保存
      </div>
    </aside>
  )
}

export default ShortlistPanel
