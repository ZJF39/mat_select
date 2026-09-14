import { useNavigate } from 'react-router-dom'
import type { MaterialCard as MaterialCardT } from '../api/types'
import { Chip } from './Chip'
import { formatRange, formatPrice, ellipsisAliases } from '../utils/format'
import './ui.css'
import '../pages/pages.css'

export interface MaterialCardProps {
  material: MaterialCardT
  onOpen?: (uid: string) => void
}

/**
 * 材料卡片（原型 03 §5.1 / 02 §01）：342×180，5 行结构 + 三列指标 + 无图片。
 * 整卡可点（role=link），无图片缩略图。
 */
export function MaterialCard({ material, onOpen }: MaterialCardProps) {
  const navigate = useNavigate()
  const open = () => (onOpen ? onOpen(material.uid) : navigate(`/materials/${material.uid}`))

  const density = formatRange(material.density_min, material.density_max)
  const temp = material.service_temp_limit == null ? '—' : String(material.service_temp_limit)
  const price = formatPrice(material.price_min, material.price_max, material.price_unit)
  const process = material.molding_process?.[0] ?? '—'

  return (
    <div
      className="ms-material-card"
      role="link"
      tabIndex={0}
      aria-label={`材料 ${material.name}`}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          open()
        }
      }}
    >
      <div className="ms-material-card__head">
        <div className="ms-ellipsis" style={{ minWidth: 0 }}>
          <div className="ms-material-card__name ms-ellipsis">{material.name}</div>
        </div>
        {material.category_name && (
          <Chip size="20" tone="accent">
            {material.category_name}
          </Chip>
        )}
      </div>

      <div className="ms-material-card__alias ms-ellipsis">
        {ellipsisAliases(material.aliases) || ' '}
      </div>

      <div className="ms-metrics">
        <div className="ms-metric">
          <div className="ms-metric__label">密度 g/cm³</div>
          <div className={`ms-metric__value${material.density_min == null && material.density_max == null ? ' ms-metric__value--empty' : ''}`}>
            {density}
          </div>
        </div>
        <div className="ms-metric-sep" />
        <div className="ms-metric">
          <div className="ms-metric__label">耐温上限 °C</div>
          <div className={`ms-metric__value${material.service_temp_limit == null ? ' ms-metric__value--empty' : ''}`}>
            {temp}
          </div>
        </div>
        <div className="ms-metric-sep" />
        <div className="ms-metric">
          <div className="ms-metric__label">参考价 元/kg</div>
          <div className={`ms-metric__value${material.price_min == null && material.price_max == null ? ' ms-metric__value--empty' : ''}`}>
            {price}
          </div>
        </div>
      </div>

      <div className="ms-row ms-gap-3 ms-wrap" style={{ minHeight: 20 }}>
        {(material.features ?? []).slice(0, 3).map((f) => (
          <Chip key={f} size="20">
            {f}
          </Chip>
        ))}
      </div>

      <div className="ms-material-card__foot">
        <span className="ms-muted" style={{ fontSize: 'var(--fs-small)' }}>推荐工艺 · {process}</span>
        <span className="ms-link" style={{ fontSize: 'var(--fs-small)' }}>查看详情 ›</span>
      </div>
    </div>
  )
}

export default MaterialCard
