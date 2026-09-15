import type { SelectionTask } from '../api/types'
import { formatTime } from '../utils/format'
import './ui.css'

export interface TaskListItemProps {
  task: SelectionTask
  active?: boolean
  onClick?: () => void
}

/** 任务列表项（原型 03 §4.3）：232×52，标题 + 元信息（推荐数·待选数·时间）。
 *  归档任务标题降饱和 + 「已归档」前缀，展开归档分组后与进行中任务可区分。 */
export function TaskListItem({ task, active, onClick }: TaskListItemProps) {
  const archived = task.status === 'archived'
  return (
    <button
      type="button"
      className={`ms-task-item${active ? ' ms-task-item--active' : ''}${archived ? ' ms-task-item--archived' : ''}`}
      aria-current={active ? 'true' : undefined}
      onClick={onClick}
    >
      <span className="ms-task-item__title ms-ellipsis">
        {archived && <span className="ms-task-item__tag">已归档</span>}
        {task.title}
      </span>
      <span className="ms-task-item__meta">
        {task.recommendation_count} 条推荐 · {task.shortlist_count} 待选 · {formatTime(task.updated_at)}
      </span>
    </button>
  )
}

export default TaskListItem
