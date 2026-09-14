import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { Notice } from '../components/Notice'
import { Skeleton, SkeletonListItem } from '../components/Skeleton'
import { toast, ToastHost } from '../components/Toast'
import './pages.css'

/** /tasks：自动落到最近一条任务，没有任务则新建一条（原型 README §3 + 05 §1.1①） */
export default function TasksPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const kicked = useRef(false)

  const tasks = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.listTasks(),
    staleTime: 10_000,
  })

  const items = tasks.data?.items

  useEffect(() => {
    if (kicked.current || !items) return
    kicked.current = true
    const actives = items.filter((t) => t.status === 'active')
    const pool = actives.length ? actives : items
    if (pool.length) {
      const best = [...pool].sort((a, b) => {
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      })[0]
      navigate(`/tasks/${best.id}`, { replace: true })
      return
    }
    api
      .createTask({ title: '新建选型任务' })
      .then((t) => {
        toast('已新建选型任务', 'success')
        qc.invalidateQueries({ queryKey: ['tasks'] })
        navigate(`/tasks/${t.id}`, { replace: true })
      })
      .catch((e) => setError(e instanceof Error ? e.message : '新建任务失败'))
  }, [items, navigate, qc])

  const retry = () => {
    kicked.current = false
    setError(null)
    tasks.refetch()
  }

  return (
    <>
      <ToastHost />
      <main className="ms-main">
        <div className="ms-page-header">
          <div>
            <h1 className="ms-page-header__title">智能推荐</h1>
            <div className="ms-page-header__sub">正在打开最近的选型任务…</div>
          </div>
        </div>

      {tasks.isError || error ? (
        <Notice tone="danger">
          <div className="ms-col" style={{ gap: 6 }}>
            <span>
              {error ?? `任务列表加载失败：${tasks.error instanceof Error ? tasks.error.message : '未知错误'}`}
            </span>
            <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={retry}>
              重试
            </button>
          </div>
        </Notice>
      ) : (
        <div className="ms-card" style={{ maxWidth: 420 }}>
          <SkeletonListItem />
          <SkeletonListItem />
          <Skeleton height={32} width={160} />
        </div>
      )}
      </main>
    </>
  )
}
