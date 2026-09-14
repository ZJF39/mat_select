/** 路由懒加载兜底（形状与实际内容一致的骨架屏，不用居中转圈） */
export function PageFallback() {
  return (
    <main className="ms-main" aria-busy="true">
      <div className="ms-skel" style={{ height: 26, width: 220 }} />
      <div className="ms-skel" style={{ height: 32, width: '100%' }} />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(342px, 1fr))',
          gap: 16,
        }}
      >
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="ms-skel-card">
            <div className="ms-skel" style={{ height: 20, width: '60%' }} />
            <div className="ms-skel" style={{ height: 12, width: '40%' }} />
            <div className="ms-skel" style={{ height: 40 }} />
            <div className="ms-skel" style={{ height: 20, width: '70%' }} />
          </div>
        ))}
      </div>
    </main>
  )
}

export default PageFallback
