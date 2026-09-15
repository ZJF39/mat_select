import { useLocation, useNavigate } from 'react-router-dom'
import { Icon, type IconName } from '../icons'

/**
 * 全局导航（原型 02 §0.2）
 * 一级导航固定 4 项；切换不销毁主区状态（本实现用 React Router 的同一 <Outlet/> 承载，
 * 会话滚动位置由页面内部维持）。
 */
interface RailItem {
  key: string
  label: string
  icon: IconName
  match: (path: string) => boolean
  to: string
}

const ITEMS: RailItem[] = [
  { key: 'materials', label: '材料库', icon: 'layers', to: '/materials', match: (p) => p.startsWith('/materials') },
  { key: 'tasks', label: '智能推荐', icon: 'sparkles', to: '/tasks', match: (p) => p.startsWith('/tasks') },
  { key: 'data', label: '数据分享', icon: 'exchange', to: '/data', match: (p) => p.startsWith('/data') },
  { key: 'settings', label: '设置', icon: 'sliders', to: '/settings', match: (p) => p.startsWith('/settings') },
]

export function NavRail() {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  return (
    <nav className="ms-rail" aria-label="一级导航">
      <div className="ms-rail__group">
        {ITEMS.map((it) => {
          const active = it.match(pathname)
          return (
            <button
              key={it.key}
              type="button"
              className={`ms-rail__item${active ? ' ms-rail__item--active' : ''}`}
              aria-current={active ? 'page' : undefined}
              onClick={() => navigate(it.to)}
            >
              <Icon name={it.icon} size={17} />
              <span>{it.label}</span>
            </button>
          )
        })}
      </div>
      {/* 版本号：需与 backend/app/core/config.py 的 APP_VERSION、里程碑 tag 三处保持一致 */}
      <div className="ms-rail__version">v1.2.4</div>
    </nav>
  )
}

export default NavRail
