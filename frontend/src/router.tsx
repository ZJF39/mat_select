import { Suspense, lazy } from 'react'
import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { PageFallback } from './layout/PageFallback'

/**
 * 路由表（原型 README §3 · 10 屏）
 * 说明：全部页面用 lazy 分包；页面文件路径由契约 §2 冻结，禁止改名。
 */
const MaterialsLibraryPage = lazy(() => import('./pages/MaterialsLibraryPage'))
const MaterialDetailPage = lazy(() => import('./pages/MaterialDetailPage'))
const MaterialEditPage = lazy(() => import('./pages/MaterialEditPage'))
const MaterialHistoryPage = lazy(() => import('./pages/MaterialHistoryPage'))
const TasksPage = lazy(() => import('./pages/TasksPage'))
const TaskWorkbenchPage = lazy(() => import('./pages/TaskWorkbenchPage'))
const ShortlistPage = lazy(() => import('./pages/ShortlistPage'))
const DataPage = lazy(() => import('./pages/DataPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

const wrap = (node: React.ReactNode) => <Suspense fallback={<PageFallback />}>{node}</Suspense>

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/materials" replace /> },
      { path: 'materials', element: wrap(<MaterialsLibraryPage />) },
      { path: 'materials/new', element: wrap(<MaterialEditPage />) },
      { path: 'materials/:uid', element: wrap(<MaterialDetailPage />) },
      { path: 'materials/:uid/edit', element: wrap(<MaterialEditPage />) },
      { path: 'materials/:uid/history', element: wrap(<MaterialHistoryPage />) },
      { path: 'tasks', element: wrap(<TasksPage />) },
      { path: 'tasks/:id', element: wrap(<TaskWorkbenchPage />) },
      { path: 'tasks/:id/shortlist', element: wrap(<ShortlistPage />) },
      { path: 'data', element: wrap(<DataPage />) },
      { path: 'settings', element: wrap(<SettingsPage />) },
      { path: '*', element: wrap(<NotFoundPage />) },
    ],
  },
])

export default router
