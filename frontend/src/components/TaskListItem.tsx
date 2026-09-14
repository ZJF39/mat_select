import type { SelectionTask } from '../api/types'
import { formatTime } from '../utils/format'
import './ui.css'

export interface TaskListItemProps {
  task: SelectionTask
  active?: boolean
  onClick?: () => void
}

/** 任务列表项（原型 03 §4.3）：232×52，标题 + 元信息（推荐数·待选数·时间）。 */
export function TaskListItem({ task, active, onClick }: TaskListItemProps) {
  return (
    <button
      type="button"
      className={`ms-task-item${active ? ' ms-task-item--active' : ''}`}
      aria-current={active ? 'true' : undefined}
      onClick={onClick}
    >
      <span className="ms-task-item__title ms-ellipsis">{task.title}</span>
      <span className="ms-task-item__meta">
        {task.recommendation_count} 条推荐 · {task.shortlist_count} 待选 · {formatTime(task.updated_at)}
      </span>
    </button>
  )
}

export default TaskListItem
