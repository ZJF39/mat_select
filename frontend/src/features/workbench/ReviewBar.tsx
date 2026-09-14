import { Icon } from '../../../icons'
import './ui.css'

export interface ReviewBarProps {
  /** 已回评结果（若有） */
  result?: 'success' | 'fail' | 'skipped' | null
  onSuccess: () => void
  onFail: () => void
  onSkip: () => void
  onEdit?: () => void
}

/** 回评条（原型 02 §04）：本次推荐有帮助吗 + 标记成功/失败/暂不评价。 */
export function ReviewBar({ result, onSuccess, onFail, onSkip, onEdit }: ReviewBarProps) {
  if (result) {
    return (
      <div className="ms-reviewbar">
        <span className="ms-reviewbar__text">
          已回评：{result === 'success' ? '成功' : result === 'fail' ? '失败' : '暂不评价'} · {new Date().toISOString().slice(0, 10)}
        </span>
        <div className="ms-reviewbar__actions">
          <button className="ms-btn ms-btn--sm ms-btn--ghost" onClick={onEdit}>修改回评</button>
        </div>
      </div>
    )
  }
  return (
    <div className="ms-reviewbar">
      <span className="ms-reviewbar__text">本次推荐有帮助吗？回评会用于调整后续排序</span>
      <div className="ms-reviewbar__actions">
        <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={onSuccess}>
          <Icon name="check" size={14} />
          标记成功
        </button>
        <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={onFail}>
          <Icon name="alert" size={14} />
          标记失败
        </button>
        <button className="ms-btn ms-btn--sm ms-btn--ghost" onClick={onSkip}>暂不评价</button>
      </div>
    </div>
  )
}

export default ReviewBar
