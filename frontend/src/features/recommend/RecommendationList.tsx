import { useEffect, useState } from 'react'
import type { Recommendation, Constraints } from '../../api/types'
import { RecommendationCard } from '../../components/RecommendationCard'
import { Notice } from '../../components/Notice'
import { Icon } from '../../icons'
import './ui.css'

export interface RecommendationListProps {
  results: Recommendation[]
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  alreadyInShortlist: (uid: string) => boolean
  onAddShortlist: (uid: string) => void
  onAdopt: (uid: string) => void
  /** 无结果时的约束描述与放宽动作 */
  emptyConstraints?: Constraints
  onRelax?: () => void
  onModify?: () => void
}

/** 推荐结果列表（原型 02 §04）：首位全展开，其余折叠；无结果不放宽就不返回（优化提示）。 */
export function RecommendationList({
  results,
  loading,
  error,
  onRetry,
  alreadyInShortlist,
  onAddShortlist,
  onAdopt,
  emptyConstraints,
  onRelax,
  onModify,
}: RecommendationListProps) {
  const [expanded, setExpanded] = useState(0)

  useEffect(() => {
    setExpanded(0)
  }, [results])

  if (error) {
    return (
      <Notice tone="danger">
        <div className="ms-col" style={{ gap: 4 }}>
          <span>{error}</span>
          {onRetry && <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={onRetry}>重试</button>}
        </div>
      </Notice>
    )
  }

  if (!loading && results.length === 0) {
    const desc =
      emptyConstraints?.temp_limit != null
        ? `没有同时满足「温度 ≤ ${emptyConstraints.temp_limit} °C${emptyConstraints.process ? ' + ' + emptyConstraints.process : ''}」的材料`
        : '没有同时满足当前硬约束的材料'
    return (
      <Notice tone="warning">
        <div className="ms-col" style={{ gap: 6 }}>
          <span>{desc}</span>
          <div className="ms-row ms-gap-3">
            {emptyConstraints?.temp_limit != null && onRelax && (
              <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={onRelax}>
                放宽温度到 {emptyConstraints.temp_limit - 10} °C 再试
              </button>
            )}
            {onModify && (
              <button className="ms-btn ms-btn--sm ms-btn--primary" onClick={onModify}>修改约束</button>
            )}
          </div>
        </div>
      </Notice>
    )
  }

  return (
    <div className="ms-col" style={{ gap: 'var(--sp-5)' }}>
      <div className="ms-rec-head">
        <span className="ms-rec-head__title">推荐结果 · 共 {results.length} 条（匹配度 ≥ 60%）</span>
        <span className="ms-rec-head__hint">匹配度由 5 个维度加权，可展开核对</span>
      </div>
      {results.map((rec, i) => (
        <RecommendationCard
          key={rec.material.uid}
          rec={rec}
          index={i + 1}
          expanded={i === expanded}
          onToggle={() => setExpanded(i === expanded ? -1 : i)}
          alreadyInShortlist={alreadyInShortlist(rec.material.uid)}
          onAddShortlist={() => onAddShortlist(rec.material.uid)}
          onAdopt={() => onAdopt(rec.material.uid)}
        />
      ))}
    </div>
  )
}

export default RecommendationList
