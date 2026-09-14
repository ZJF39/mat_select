import type { ThemeConfig } from 'antd'

/**
 * AntD 5 主题覆盖（来源：doc/前端原型/01-设计规范-DesignTokens.md §7）
 * 6 项必覆盖：主色 / 圆角(5·7·10) / 控件高度(32·34) / 字体族与字号 / 表格行高46·表头底色 / Modal 圆角与遮罩
 */
export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#1F5FD0',
    colorSuccess: '#2E9E6B',
    colorWarning: '#C9821B',
    colorError: '#D2433E',
    colorInfo: '#1F5FD0',
    colorText: '#15171C',
    colorTextSecondary: '#565E6B',
    colorTextTertiary: '#8A93A1',
    colorBgLayout: '#F4F5F7',
    colorBgContainer: '#FFFFFF',
    colorBorder: '#E4E6EB',
    colorBorderSecondary: '#EFF1F4',
    borderRadius: 7,
    borderRadiusLG: 10,
    borderRadiusSM: 5,
    controlHeight: 32,
    controlHeightLG: 34,
    fontSize: 12,
    fontFamily: '"Noto Sans SC", system-ui, "PingFang SC", "Microsoft YaHei", sans-serif',
    fontFamilyCode: '"Geist Mono", ui-monospace, monospace',
    boxShadow: 'none',
    boxShadowSecondary: 'none',
    wireframe: false,
  },
  components: {
    Table: {
      headerBg: '#F7F8FA',
      headerColor: '#7A8494',
      headerSplitColor: 'transparent',
      rowHoverBg: '#F7F8FA',
      cellPaddingBlock: 14,
      borderColor: '#EFF1F4',
      fontSize: 12,
    },
    Modal: { borderRadiusLG: 14, contentBg: '#FFFFFF', titleFontSize: 15 },
    Button: { fontWeight: 500, primaryShadow: 'none', defaultShadow: 'none' },
    Input: { paddingInline: 10, activeShadow: 'none' },
    Segmented: { itemSelectedBg: '#EAEFFB', itemSelectedColor: '#1F5FD0' },
    Slider: {
      trackBg: '#1F5FD0',
      railBg: '#EEF0F3',
      handleColor: '#FFFFFF',
      handleSize: 14,
      railSize: 8,
    },
    Tooltip: { colorBgSpotlight: '#15171C', borderRadius: 6, fontSize: 11 },
  },
}
