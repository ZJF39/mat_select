import './ui.css'

export interface ParamRowProps {
  label: string
  value: string
  emphasis?: boolean
  empty?: boolean
  mono?: boolean
}

/** 参数行（原型 03 §5.5 / app.css .ms-param-row）：label 左 / value 右（等宽）。 */
export function ParamRow({ label, value, emphasis, empty, mono = true }: ParamRowProps) {
  return (
    <div className={`ms-param-row${emphasis ? ' ms-param-row--emphasis' : ''}`}>
      <span className="ms-param-row__label">{label}</span>
      <span
        className={`ms-param-row__value${empty ? ' ms-param-row__value--empty' : ''}${mono ? '' : ''}`}
      >
        {value}
      </span>
    </div>
  )
}

export default ParamRow
