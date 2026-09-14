import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CategoryNode } from '../api/types'
import { Icon } from '../icons'
import './ui.css'

export interface CategoryTreeProps {
  nodes: CategoryNode[]
  selectedId?: number | null
  onSelect?: (id: number | null) => void
  /** 显示「管理分类体系 →」（默认 true） */
  showManage?: boolean
}

/** 分类树（原型 02 §0.3 / 03 §4.2）：两级 + 计数 + 「管理分类体系 →」。 */
export function CategoryTree({ nodes, selectedId, onSelect, showManage = true }: CategoryTreeProps) {
  const navigate = useNavigate()
  const [open, setOpen] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(nodes.map((n) => [n.id, true])),
  )
  const treeRef = useRef<HTMLDivElement>(null)

  /** ↑/↓ 在当前展开树的可见行之间移动焦点（K-01） */
  const moveFocus = (from: HTMLElement, dir: 1 | -1) => {
    const items = Array.from(treeRef.current?.querySelectorAll<HTMLElement>('[role="treeitem"]') ?? [])
    const i = items.indexOf(from)
    items[i + dir]?.focus()
  }

  const Row = ({
    node,
    level,
  }: {
    node: CategoryNode
    level: number
  }) => {
    const hasChildren = !!node.children?.length
    const active = selectedId === node.id
    const expanded = open[node.id]
    return (
      <>
        <div
          className={`ms-tree-row${active ? ' ms-tree-row--active' : ''}`}
          style={{ paddingLeft: level === 0 ? 10 : 26 }}
          role="treeitem"
          aria-selected={active}
          aria-expanded={hasChildren ? expanded : undefined}
          tabIndex={0}
          onClick={() => onSelect?.(node.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onSelect?.(node.id)
            } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
              e.preventDefault()
              moveFocus(e.currentTarget, e.key === 'ArrowDown' ? 1 : -1)
            } else if (hasChildren && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
              setOpen((s) => ({ ...s, [node.id]: e.key === 'ArrowRight' }))
            }
          }}
        >
          {hasChildren ? (
            <span
              className={`ms-tree-row__chev${expanded ? ' ms-tree-row__chev--open' : ''}`}
              onClick={(e) => {
                e.stopPropagation()
                setOpen((s) => ({ ...s, [node.id]: !expanded }))
              }}
            >
              <Icon name="chevronRight" size={10} />
            </span>
          ) : (
            <span className="ms-tree-row__leaf-icon" />
          )}
          <span className="ms-ellipsis" style={{ flex: 1, minWidth: 0 }}>
            {node.name}
          </span>
          <span className="ms-tree-row__count">{node.count}</span>
        </div>
        {hasChildren &&
          expanded &&
          node.children!.map((c) => <Row key={c.id} node={c} level={level + 1} />)}
      </>
    )
  }

  return (
    <>
      <div role="tree" ref={treeRef}>
        <div
          className={`ms-tree-row${selectedId == null ? ' ms-tree-row--active' : ''}`}
          style={{ paddingLeft: 10 }}
          role="treeitem"
          aria-selected={selectedId == null}
          tabIndex={0}
          onClick={() => onSelect?.(null)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onSelect?.(null)
            } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
              e.preventDefault()
              moveFocus(e.currentTarget, e.key === 'ArrowDown' ? 1 : -1)
            }
          }}
        >
          <span className="ms-tree-row__leaf-icon" />
          <span style={{ flex: 1 }}>全部分类</span>
          <span className="ms-tree-row__count">
            {nodes.reduce((s, n) => s + n.count + (n.children?.reduce((c, ch) => c + ch.count, 0) ?? 0), 0)}
          </span>
        </div>
        {nodes.map((n) => (
          <Row key={n.id} node={n} level={0} />
        ))}
        {nodes.length === 0 && (
          <div className="ms-muted" style={{ padding: 'var(--sp-3) 10px', fontSize: 'var(--fs-small)' }}>
            暂无分类，可在「管理分类体系」中创建
          </div>
        )}
      </div>
      {showManage && (
        <div style={{ marginTop: 'var(--sp-4)', paddingLeft: 10 }}>
          <button className="ms-link" style={{ fontSize: 'var(--fs-small)', background: 'none', border: 'none' }} onClick={() => navigate('/settings')}>
            管理分类体系 ›
          </button>
        </div>
      )}
    </>
  )
}

export default CategoryTree
