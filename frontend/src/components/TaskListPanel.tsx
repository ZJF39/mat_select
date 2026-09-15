import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { SelectionTask } from '../api/types'
import { SidePanel } from '../layout/SidePanel'
import { TaskListItem } from './TaskListItem'
import { EmptyState } from './EmptyState'
import { SkeletonListItem } from './Skeleton'
import { Icon } from '../icons'
import { Notice } from './Notice'
import './ui.css'

export interface TaskListPanelProps {
  tasks: SelectionTask[]
  activeId?: number
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  onCreate?: () => void
  onSelect?: (id: number) => void
}

/** 任务列表面板（原型 02 §0.3 / 03 §4.3）：头（标题+计数+新建主按钮）+ 进行中 + 已归档（可折叠）+ 个人数据说明。 */
export function TaskListPanel({
  tasks,
  activeId,
  loading,
  error,
  onRetry,
  onCreate,
  onSelect,
}: TaskListPanelProps) {
  const navigate = useNavigate()
  const active = tasks.filter((t) => t.status === 'active')
  const archived = tasks.filter((t) => t.status === 'archived')
  const select = (id: number) => (onSelect ? onSelect(id) : navigate(`/tasks/${id}`))

  // 归档分组默认折叠，避免长期使用后把「进行中」任务挤出可视区。
  const [archivedOpen, setArchivedOpen] = useState(false)

  // 但当前打开的就是归档任务时（直接点归档项 / 从 URL 进入），必须自动展开，
  // 否则左侧列表里看不到任何高亮项，用户会以为任务丢了。
  const activeIsArchived = activeId != null && archived.some((t) => t.id === activeId)
  useEffect(() => {
    if (activeIsArchived) setArchivedOpen(true)
  }, [activeIsArchived])

  return (
    <SidePanel
      title="选型任务"
      sub={`共 ${tasks.length} 个`}
      headExtra={
        <button className="ms-btn ms-btn--primary ms-btn--sm" onClick={onCreate ?? (() => navigate('/tasks'))}>
          <Icon name="plus" size={14} />
          新建选型任务
        </button>
      }
      foot={<span>任务与待选为本地工作数据，不写入材料主库、不参与推荐排序。</span>}
    >
      {error ? (
        <Notice tone="danger">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span>{error}</span>
            {onRetry && (
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={onRetry}>
                重试
              </button>
            )}
          </div>
        </Notice>
      ) : loading ? (
        <>
          <SkeletonListItem />
          <SkeletonListItem />
          <SkeletonListItem />
          <SkeletonListItem />
        </>
      ) : tasks.length === 0 ? (
        <EmptyState
          icon="sparkles"
          title="还没有任务"
          desc="输入一句话开始选材，例如「保险丝座，耐温 150°C，注塑」"
          action={
            <button className="ms-btn ms-btn--primary ms-btn--sm" onClick={onCreate ?? (() => navigate('/tasks'))}>
              新建选型任务
            </button>
          }
        />
      ) : (
        <div className="ms-tasklist">
          {active.length > 0 && (
            <>
              <div className="ms-tasklist__group-label">进行中（{active.length}）</div>
              {active.map((t) => (
                <TaskListItem key={t.id} task={t} active={t.id === activeId} onClick={() => select(t.id)} />
              ))}
            </>
          )}
          {active.length === 0 && (
            <div className="ms-tasklist__group-label">没有进行中的任务，可从下方归档任务中复制新任务</div>
          )}

          {archived.length > 0 && (
            <>
              {/* 折叠头：整行可点，chevron 指示开合（原型 03 §4.3 的「已归档任务 ›」） */}
              <button
                type="button"
                className="ms-tasklist__group-toggle"
                aria-expanded={archivedOpen}
                onClick={() => setArchivedOpen((o) => !o)}
              >
                <span
                  className={`ms-tasklist__chev${archivedOpen ? ' ms-tasklist__chev--open' : ''}`}
                  aria-hidden
                >
                  <Icon name="chevronRight" size={10} />
                </span>
                <span>已归档任务（{archived.length}）</span>
              </button>
              {archivedOpen &&
                archived.map((t) => (
                  <TaskListItem key={t.id} task={t} active={t.id === activeId} onClick={() => select(t.id)} />
                ))}
            </>
          )}
        </div>
      )}
    </SidePanel>
  )
}

export default TaskListPanel
