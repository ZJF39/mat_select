import { Icon } from '../../../icons'
import { Chip } from '../../../components/Chip'
import { useNavigate } from 'react-router-dom'
import './ui.css'

export interface SessionHeaderProps {
  title: string
  statusLabel?: string
  archived?: boolean
  onRename: () => void
  onPin: () => void
  onArchive: () => void
  onExport: () => void
}

/** 会话头（原型 02 §04）：任务名 + 状态 Chip + 重命名/置顶/归档/导出为 Markdown。 */
export function SessionHeader({ title, statusLabel, archived, onRename, onPin, onArchive, onExport }: SessionHeaderProps) {
  const navigate = useNavigate()
  return (
    <div className="ms-wb__head">
      <span className="ms-wb__head-title ms-ellipsis">{title}</span>
      {statusLabel && <Chip size="20" tone="success">{statusLabel}</Chip>}
      <div className="ms-wb__head-actions">
        <button className="ms-icon-btn" aria-label="重命名" title="重命名" onClick={onRename}><Icon name="edit" size={16} /></button>
        <button className="ms-icon-btn" aria-label="置顶" title="置顶" onClick={onPin}><Icon name="pin" size={16} /></button>
        <button className="ms-icon-btn" aria-label="归档" title="归档" onClick={onArchive}><Icon name="archive" size={16} /></button>
        <button className="ms-icon-btn" aria-label="导出为 Markdown" title="导出为 Markdown" onClick={onExport}><Icon name="download" size={16} /></button>
        {archived && (
          <button className="ms-btn ms-btn--sm ms-btn--ghost" onClick={() => navigate('/tasks')}>复制为新任务</button>
        )}
      </div>
    </div>
  )
}

export default SessionHeader
