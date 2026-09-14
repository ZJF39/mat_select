import type { ReactNode } from 'react'

/**
 * 列表面板容器（原型 02 §0.3）：两种形态共用同一外壳
 * - 分类树面板（材料库/详情/编辑/history）
 * - 任务列表面板（工作台/待选清单）
 * 只负责宽 264 / 白底 / 上标题下滚动 的骨架，内容由页面注入。
 */
export function SidePanel({
  title,
  sub,
  headExtra,
  foot,
  children,
  collapsed,
}: {
  title: ReactNode
  sub?: ReactNode
  headExtra?: ReactNode
  foot?: ReactNode
  children: ReactNode
  collapsed?: boolean
}) {
  if (collapsed) return null
  return (
    <aside className="ms-panel" aria-label="侧边面板">
      <div className="ms-panel__head">
        <div className="ms-row" style={{ justifyContent: 'space-between', gap: 'var(--sp-4)' }}>
          <span className="ms-panel__title">{title}</span>
          {headExtra}
        </div>
        {sub && <div className="ms-panel__sub">{sub}</div>}
      </div>
      <div className="ms-panel__body">{children}</div>
      {foot && <div className="ms-panel__foot">{foot}</div>}
    </aside>
  )
}

export default SidePanel
