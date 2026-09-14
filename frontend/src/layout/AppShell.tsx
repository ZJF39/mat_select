import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'
import { TopBar } from './TopBar'
import { NavRail } from './NavRail'
import './layout.css'

/**
 * 全局骨架（原型 02 §0）：TopBar h56 → [NavRail w68 | 页面主体]
 * 页面主体由路由页面自行组织（可再嵌入 SidePanel），保证「主内容区唯一滚动层」。
 */
export function AppShell({ children }: { children?: ReactNode }) {
  return (
    <div className="ms-app">
      <TopBar />
      <div className="ms-app__body">
        <NavRail />
        {children ?? <Outlet />}
      </div>
    </div>
  )
}

export default AppShell
