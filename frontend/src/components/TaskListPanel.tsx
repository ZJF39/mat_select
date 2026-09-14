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

/** 任务列表面板（原型 02 §0.3 / 03 §4.3）：头（标题+计数+新建主按钮）+ 分组 + 任务项 + 已归档 + 个人数据说明。 */
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
          <div className="ms-tasklist__group-label">进行中</div>
          {active.map((t) => (
            <TaskListItem key={t.id} task={t} active={t.id === activeId} onClick={() => select(t.id)} />
          ))}
          {archived.length > 0 && (
            <>
              <div className="ms-tasklist__group-label" style={{ marginTop: 'var(--sp-4)' }}>
                已归档任务（{archived.length}）›
              </div>
              {archived.map((t) => (
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
