/**
 * MatSelect · Tailwind 主题片段（与 tokens.css 同源）
 *
 * 用法（Tailwind v3，tailwind.config.js）：
 *   const msTokens = require('./src/styles/tailwind.tokens.js')
 *   module.exports = { content: [...], theme: { extend: msTokens } }
 *
 * 用法（Tailwind v4，CSS 内 @theme）：
 *   直接 @import 本目录的 tokens.css，用 var(--color-accent) 取值，
 *   或把下方对象逐项搬进 @theme { --color-accent: #1F5FD0; ... }
 */

module.exports = {
  colors: {
    accent: {
      DEFAULT: '#1F5FD0',
      hover: '#1A4FAE',
      soft: '#EAEFFB',
      'soft-border': '#C6D5F4',
      strong: '#1A3557',
      text: '#1A4FAE',
    },
    app: '#F4F5F7',
    surface: '#FFFFFF',
    subtle: '#F7F8FA',
    sunken: '#F2F4F7',
    'panel-alt': '#FBFCFD',
    line: {
      DEFAULT: '#E4E6EB',
      control: '#DDE1E7',
      row: '#EFF1F4',
      divider: '#E9ECF1',
      track: '#EEF0F3',
    },
    ink: {
      1: '#15171C',
      2: '#3F4855',
      3: '#565E6B',
      4: '#7A8494',
      5: '#8A93A1',
      6: '#98A1AE',
      7: '#AAB2BD',
      8: '#B4BBC5',
      muted: '#6B7482',
    },
    success: { DEFAULT: '#2E9E6B', strong: '#1D6B47', soft: '#E7F5EE' },
    warning: { DEFAULT: '#C9821B', strong: '#8A5A12', soft: '#FDF3E4' },
    danger:  { DEFAULT: '#D2433E', strong: '#A5322E', soft: '#FCECEB' },
    info:    { DEFAULT: '#1A4FAE', soft: '#EAF0FC' },
  },

  fontFamily: {
    sans: ['"Noto Sans SC"', 'system-ui', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
    mono: ['"Geist Mono"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
  },

  fontSize: {
    display: ['20px', '26px'],
    h1: ['15px', '20px'],
    h2: ['14px', '19px'],
    h3: ['13px', '18px'],
    body: ['12px', '18px'],
    small: ['11px', '17px'],
    caption: ['10px', '15px'],
    micro: ['9px', '12px'],
  },

  fontWeight: { regular: '400', medium: '500', semibold: '600' },

  spacing: {
    1: '2px',
    2: '4px',
    3: '6px',
    4: '8px',
    5: '10px',
    6: '12px',
    7: '14px',
    8: '16px',
    9: '18px',
    10: '20px',
    12: '24px',
    topbar: '56px',
    rail: '68px',
    panel: '264px',
    shortlist: '300px',
  },

  borderRadius: {
    xs: '4px',
    sm: '5px',
    md: '6px',
    lg: '7px',
    xl: '8px',
    '2xl': '10px',
    '3xl': '12px',
    '4xl': '14px',
  },

  boxShadow: {
    none: 'none',
    modal: '0 18px 44px -6px rgba(15, 20, 28, 0.24)',
  },

  height: {
    topbar: '56px',
    control: '32px',
    'control-lg': '34px',
    'control-sm': '26px',
    'icon-btn': '26px',
    row: '46px',
    thead: '42px',
    card: '180px',
  },

  width: {
    rail: '68px',
    panel: '264px',
    shortlist: '300px',
    card: '342px',
  },

  transitionTimingFunction: {
    out: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
  },
  transitionDuration: { fast: '120ms', base: '180ms', modal: '220ms' },
}
