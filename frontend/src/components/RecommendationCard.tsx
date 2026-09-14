import { useNavigate } from 'react-router-dom'
import type { Recommendation, ScoreBreakdown } from '../api/types'
import { Chip } from './Chip'
import { Tooltip } from './Tooltip'
import { Icon } from '../icons'
import { pct } from '../utils/format'
import './ui.css'

const DIM_LABEL: Record<keyof Omit<ScoreBreakdown, 'feedback_penalty'>, string> = {
  temp: '温度裕度',
  semantic: '语义场景',
  cost: '成本匹配',
  mechanics: '力学性能',
  process: '工艺适配',
}
const DIM_TIP: Record<keyof Omit<ScoreBreakdown, 'feedback_penalty'>, string> = {
  temp: '需求温度与材料耐温上限的裕度，过大同样扣分（避免过度设计）',
  semantic: '候选集内材料场景/特性文本与需求的语义相似度',
  cost: '材料价格与预算区间的匹配度',
  mechanics: '按零件类型推断的关键力学性能匹配',
  process: '推荐成型工艺与需求的适配度',
}

export interface RecommendationCardProps {
  rec: Recommendation
  index: number
  expanded: boolean
  onToggle: () => void
  alreadyInShortlist?: boolean
  onAddShortlist?: () => void
  onAdopt?: () => void
}

/** 推荐卡片（原型 02 §04）：展开/折叠两态 + 分数拆解条(Tooltip) + 理由/关键参数/注意/替代 + 标记采用/加入待选。 */
export function RecommendationCard({
  rec,
  index,
  expanded,
  onToggle,
  alreadyInShortlist,
  onAddShortlist,
  onAdopt,
}: RecommendationCardProps) {
  const navigate = useNavigate()
  const m = rec.material
  const breakdown = rec.breakdown

  const dims = (Object.keys(DIM_LABEL) as (keyof typeof DIM_LABEL)[]).map((k) => ({
    key: k,
    label: DIM_LABEL[k],
    tip: DIM_TIP[k],
    got: breakdown[k].got,
    max: breakdown[k].max,
  }))

  if (!expanded) {
    return (
      <div
        className="ms-rec-card ms-rec-card--collapsed"
        role="button"
        tabIndex={0}
        aria-expanded={false}
        onClick={onToggle}
        onKeyDown={(e) => e.key === 'Enter' && onToggle()}
      >
        <span className="ms-rec-card__seq">{index}</span>
        <span className="ms-rec-card__name ms-ellipsis">{m.name}</span>
        <Chip size="26" tone="success" ariaLabel={`匹配度 ${pct(rec.score)}`}>匹配度 {pct(rec.score)}</Chip>
        <div className="ms-rec-card__actions" onClick={(e) => e.stopPropagation()}>
          {onAdopt && (
            <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={onAdopt}>
              标记采用
            </button>
          )}
          {onAddShortlist && (
            <button className="ms-btn ms-btn--sm ms-btn--primary" disabled={alreadyInShortlist} onClick={onAddShortlist}>
              {alreadyInShortlist ? '已在待选 ✓' : '加入待选'}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="ms-rec-card">
      <div className="ms-rec-card__top">
        <span className="ms-rec-card__seq">{index}</span>
        <span className="ms-rec-card__name">{m.name}</span>
        {m.category_name && <Chip size="20" tone="accent">{m.category_name}</Chip>}
        <div className="ms-rec-card__actions">
          <Chip size="26" tone="success" ariaLabel={`匹配度 ${pct(rec.score)}`}>匹配度 {pct(rec.score)}</Chip>
          {onAdopt && (
            <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={onAdopt}>
              标记采用
            </button>
          )}
          {onAddShortlist && (
            <button className="ms-btn ms-btn--sm ms-btn--primary" disabled={alreadyInShortlist} onClick={onAddShortlist}>
              {alreadyInShortlist ? '已在待选 ✓' : '加入待选'}
            </button>
          )}
        </div>
      </div>

      <div className="ms-breakdown" aria-label="匹配度分数拆解">
        {dims.map((d) => (
          <Tooltip key={d.key} content={d.tip}>
            <span className="ms-breakdown__item">
              <span className="ms-breakdown__dim">{d.label}</span>
              <span className="ms-breakdown__val" aria-label={`${d.label} 得分 ${d.got}，满分 ${d.max}`}>{d.got}/{d.max}</span>
            </span>
          </Tooltip>
        ))}
        {breakdown.feedback_penalty < 0 && (
          <span className="ms-breakdown__item ms-breakdown__penalty">
            <span className="ms-breakdown__dim">反馈修正</span>
            <span>{breakdown.feedback_penalty}</span>
          </span>
        )}
      </div>

      <div>
        <div className="ms-rec-card__label">推荐理由</div>
        <div className="ms-rec-card__reason">{rec.reason}</div>
      </div>

      <div>
        <div className="ms-rec-card__label">关键参数</div>
        <div className="ms-rec-card__keyparams">{rec.key_params.join(' · ')}</div>
      </div>

      {rec.cautions.length > 0 && (
        <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start', color: 'var(--warning-strong)', fontSize: 'var(--fs-body)' }}>
          <Icon name="alert" size={14} style={{ flex: 'none', marginTop: 2 }} />
          <span style={{ lineHeight: '17px' }}>{rec.cautions.join('；')}</span>
        </div>
      )}

      {rec.alternatives.length > 0 && (
        <div>
          <div className="ms-rec-card__label">替代方案</div>
          <div className="ms-rec-card__keyparams">
            {rec.alternatives
              .map((a) => `${a.name}（匹配度 ${pct(a.score)}%，${a.tradeoff}）`)
              .join(' · ')}
          </div>
        </div>
      )}

      <button
        className="ms-link"
        style={{ alignSelf: 'flex-start', background: 'none', border: 'none', fontSize: 'var(--fs-small)' }}
        onClick={() => navigate(`/materials/${m.uid}`)}
      >
        查看材料详情 ›
      </button>
    </div>
  )
}

export default RecommendationCard
