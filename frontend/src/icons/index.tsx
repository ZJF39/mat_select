/**
 * MatSelect 图标集（线性描边，stroke-width 1.8，viewBox 24×24）
 * 归属：技术负责人（冻结）。全站禁止用 emoji / Unicode 字符（✓ ★ ⚠）代替图标。
 * 用法：<Icon name="search" size={14} />  颜色继承 currentColor。
 */
import type { CSSProperties } from 'react'

export type IconName =
  | 'search'
  | 'download'
  | 'upload'
  | 'layers'
  | 'sparkles'
  | 'exchange'
  | 'sliders'
  | 'chevronDown'
  | 'chevronUp'
  | 'chevronLeft'
  | 'chevronRight'
  | 'close'
  | 'grip'
  | 'edit'
  | 'clock'
  | 'more'
  | 'arrowRight'
  | 'alert'
  | 'info'
  | 'danger'
  | 'plus'
  | 'check'
  | 'trash'
  | 'pin'
  | 'archive'
  | 'fileText'
  | 'refresh'
  | 'external'
  | 'flask'
  | 'shield'
  | 'database'

const paths: Record<IconName, React.ReactNode> = {
  search: (<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>),
  download: (<><path d="M12 3v12" /><path d="M7 11l5 5 5-5" /><path d="M5 20h14" /></>),
  upload: (<><path d="M12 20V8" /><path d="M7 12l5-5 5 5" /><path d="M5 4h14" /></>),
  layers: (<><path d="M12 3l8 4.5-8 4.5-8-4.5L12 3z" /><path d="M4 12l8 4.5 8-4.5" /><path d="M4 16.5L12 21l8-4.5" /></>),
  sparkles: (<><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" /><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z" /></>),
  exchange: (<><path d="M4 8h13l-3-3" /><path d="M20 16H7l3 3" /></>),
  sliders: (<><path d="M5 6h14" /><path d="M5 12h14" /><path d="M5 18h14" /><circle cx="9" cy="6" r="2" /><circle cx="15" cy="12" r="2" /><circle cx="10" cy="18" r="2" /></>),
  chevronDown: (<path d="M6 9l6 6 6-6" />),
  chevronUp: (<path d="M6 15l6-6 6 6" />),
  chevronLeft: (<path d="M15 6l-6 6 6 6" />),
  chevronRight: (<path d="M9 6l6 6-6 6" />),
  close: (<><path d="M6 6l12 12" /><path d="M18 6L6 18" /></>),
  grip: (<><circle cx="9" cy="6" r="1" /><circle cx="15" cy="6" r="1" /><circle cx="9" cy="12" r="1" /><circle cx="15" cy="12" r="1" /><circle cx="9" cy="18" r="1" /><circle cx="15" cy="18" r="1" /></>),
  edit: (<><path d="M4 20h4l10-10-4-4L4 16v4z" /><path d="M14 6l4 4" /></>),
  clock: (<><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></>),
  more: (<><circle cx="6" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="18" cy="12" r="1" /></>),
  arrowRight: (<><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></>),
  alert: (<><path d="M12 4l9 16H3L12 4z" /><path d="M12 10v4" /><path d="M12 17h.01" /></>),
  info: (<><circle cx="12" cy="12" r="8" /><path d="M12 11v5" /><path d="M12 8h.01" /></>),
  danger: (<><circle cx="12" cy="12" r="8" /><path d="M12 8v5" /><path d="M12 16h.01" /></>),
  plus: (<><path d="M12 5v14" /><path d="M5 12h14" /></>),
  check: (<path d="M5 13l4 4 10-10" />),
  trash: (<><path d="M4 7h16" /><path d="M9 7V5h6v2" /><path d="M6 7l1 13h10l1-13" /></>),
  pin: (<><path d="M12 3l2 5 5 .5-3.5 3.5L17 19l-5-2.5L7 19l1.5-7L5 8.5 10 8l2-5z" /></>),
  archive: (<><path d="M4 7h16v13H4z" /><path d="M3 4h18v3H3z" /><path d="M10 12h4" /></>),
  fileText: (<><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M9 12h6" /><path d="M9 16h6" /></>),
  refresh: (<><path d="M20 11a8 8 0 1 0-2 6" /><path d="M20 5v6h-6" /></>),
  external: (<><path d="M14 4h6v6" /><path d="M20 4l-8 8" /><path d="M18 14v6H4V6h6" /></>),
  flask: (<><path d="M9 3h6" /><path d="M10 3v6L5 19h14L13 9V3" /><path d="M7 15h10" /></>),
  shield: (<><path d="M12 3l7 3v6c0 5-3 7-7 9-4-2-7-4-7-9V6l7-3z" /><path d="M9 12l2 2 4-4" /></>),
  database: (<><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></>),
}

export interface IconProps {
  name: IconName
  size?: number
  className?: string
  style?: CSSProperties
  strokeWidth?: number
}

export function Icon({ name, size = 14, className, style, strokeWidth = 1.8 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
      focusable="false"
    >
      {paths[name]}
    </svg>
  )
}

export default Icon
