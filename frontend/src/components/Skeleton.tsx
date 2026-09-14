import './ui.css'

export interface SkeletonProps {
  width?: number | string
  height?: number | string
  radius?: number | string
  style?: React.CSSProperties
  className?: string
}

/** 骨架条（形状与实际内容一致；不用居中转圈）。 */
export function Skeleton({ width, height = 12, radius = 6, style, className = '' }: SkeletonProps) {
  return (
    <div
      className={`ms-skel ${className}`}
      style={{ width: width ?? '100%', height, borderRadius: radius, ...style }}
    />
  )
}

/** 卡片骨架（保留 342×180 外框，内部置灰条）。 */
export function SkeletonCard() {
  return (
    <div className="ms-skel-card">
      <div className="ms-skel" style={{ height: 20, width: '60%' }} />
      <div className="ms-skel" style={{ height: 12, width: '40%' }} />
      <div className="ms-skel" style={{ height: 40 }} />
      <div className="ms-skel" style={{ height: 20, width: '70%' }} />
      <div className="ms-skel" style={{ height: 16, width: '50%' }} />
    </div>
  )
}

/** 表格行骨架。 */
export function SkeletonRow({ cols = 9 }: { cols?: number }) {
  return (
    <div className="ms-row" style={{ gap: 12, padding: '0 12px', height: 46, borderBottom: '1px solid var(--border-row)' }}>
      {Array.from({ length: cols }).map((_, i) => (
        <div key={i} className="ms-skel" style={{ height: 12, flex: i === 0 ? 1.6 : 1, width: i === 0 ? undefined : 80 }} />
      ))}
    </div>
  )
}

/** 树行骨架。 */
export function SkeletonTreeRow() {
  return <div className="ms-skel" style={{ height: 30, borderRadius: 6, margin: '0 8px' }} />
}

/** 列表项骨架。 */
export function SkeletonListItem() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '10px 12px' }}>
      <div className="ms-skel" style={{ height: 14, width: '70%' }} />
      <div className="ms-skel" style={{ height: 10, width: '50%' }} />
    </div>
  )
}

export default Skeleton
