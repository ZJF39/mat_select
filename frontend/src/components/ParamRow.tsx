import './ui.css'

export interface ParamRowProps {
  label: string
  value: string
  /** 计量单位：显示在数值**之后**（如 密度 1.1–1.2 g/cm³）。空值时仍跟随占位符 — 展示 */
  unit?: string
  emphasis?: boolean
  empty?: boolean
  /** 兼容旧调用（详情页「推荐成型工艺」）。当前 .ms-param-row__value 恒为等宽字体，此参数无实际作用 */
  mono?: boolean
}

/** 参数行（原型 03 §5.5 / app.css .ms-param-row）：label 左 / value 右（等宽）。
 *  列表态（.ms-param-list 内）由 pages.css 改写为「名称 | 数值+单位」两列网格：
 *  数值紧随物理量、单位缀于数值后、行间以浅色细线分隔。 */
export function ParamRow({ label, value, unit, emphasis, empty }: ParamRowProps) {
  return (
    <div className={`ms-param-row${emphasis ? ' ms-param-row--emphasis' : ''}`}>
      <span className="ms-param-row__label">{label}</span>
      <span
        className={`ms-param-row__value${empty ? ' ms-param-row__value--empty' : ''}`}
      >
        {value}
        {unit ? <span className="ms-param-row__unit">{unit}</span> : null}
      </span>
    </div>
  )
}

export default ParamRow
