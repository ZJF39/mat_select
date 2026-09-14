# 01 · 设计规范 / Design Tokens

> 全部数值来自原型定稿。**任何未在此表出现的颜色、字号、间距都不得进入代码。**

---

## 1. 颜色

### 1.1 主色（唯一强调色，饱和度 < 80%，无渐变、无外发光）

| Token | 值 | 用途 | 出现屏 |
| --- | --- | --- | --- |
| `--color-accent` | `#1F5FD0` | 主按钮底、选中态文字、链接、滑杆已填充 | 全站 |
| `--color-accent-soft` | `#EAEFFB` | 选中项背景、次级高亮块、选中 Chip | 全站 |
| `--color-accent-soft-border` | `#C6D5F4` | 选中态描边（如回评「失败」选中） | 06 |
| `--color-accent-strong` | `#1A3557` | 用户气泡内的正文（在 accent-soft 上） | 04 |
| `--color-accent-text` | `#1A4FAE` | 信息提示条文字 | 多处 |
| `--color-accent-hover` | `#1A4FAE` | **建议值，原型未画**：主按钮 hover | — |

### 1.2 中性色（冷灰系，单一色相，全站不混暖灰）

| Token | 值 | 用途 |
| --- | --- | --- |
| `--bg-app` | `#F4F5F7` | 应用底色（导航右侧主区背景） |
| `--bg-surface` | `#FFFFFF` | 卡片 / 面板 / 输入框 / 顶栏 |
| `--bg-subtle` | `#F7F8FA` | 表头、次级卡片、代码块、滑杆槽外层 |
| `--bg-sunken` | `#F2F4F7` | Chip 默认底、全局搜索框底 |
| `--bg-panel-alt` | `#FBFCFD` | 待选清单面板底（与主区白色区分） |
| `--border` | `#E4E6EB` | 卡片 / 面板 / 分区线（1px） |
| `--border-control` | `#DDE1E7` | 输入框、次级按钮描边 |
| `--border-row` | `#EFF1F4` | 表格行分隔线 |
| `--border-divider` | `#E9ECF1` | 卡片内竖向分隔（如指标列之间） |
| `--border-track` | `#EEF0F3` | 滑杆轨道 |

### 1.3 文字层级

| Token | 值 | 字号区间 | 用途 |
| --- | --- | --- | --- |
| `--text-1` | `#15171C` | 15–20px | 页面标题、材料名、数值主值 |
| `--text-2` | `#3F4855` | 12–13px | 正文、按钮文字、表格单元格 |
| `--text-3` | `#565E6B` | 11–12px | 标签、说明、参数行 label |
| `--text-4` | `#7A8494` | 11px | 表头文字、图标默认色 |
| `--text-5` | `#8A93A1` | 10–11px | 元信息、副标题、单位 |
| `--text-6` | `#98A1AE` | 10px | 分组小标题、计数 |
| `--text-7` | `#AAB2BD` | 10px | 占位符、脚注提示 |
| `--text-8` | `#B4BBC5` | 9–10px | 拖拽手柄、版本号 |

> ⚠️ `--text-5 ~ --text-8` 白底对比度仅 3.1–2.4:1，**只允许用于非关键信息**。承载决策信息的文本请用 `--text-3` 或 `#6B7482`（见 §6）。

### 1.4 语义色（成对使用：底 + 文字）

| 语义 | 底 | 文字 | 深色文字（用于状态文字/徽章） | 用途 |
| --- | --- | --- | --- | --- |
| 成功 | `#E7F5EE` | `#2E9E6B` | `#1D6B47` | 匹配度徽章、回评「成功」、导入「新增」、diff「新增」 |
| 警示 | `#FDF3E4` | `#C9821B` | `#8A5A12` | 注意事项提示条、待验证标记、diff「修改」 |
| 危险 | `#FCECEB` | `#D2433E` | `#A5322E` | 历史反馈降权、校验失败、diff「删除」、清空反馈 |
| 信息 | `#EAF0FC` | `#1F5FD0` | `#1A4FAE` | 规则说明、导入「更新」、字段提示 |

### 1.5 遮罩

| Token | 值 | 用途 |
| --- | --- | --- |
| `--scrim` | `rgba(15, 20, 28, 0.45)` | Modal 遮罩（06 屏） |

### 1.6 强调用色红线

- **禁止**：纯黑 `#000000`、霓虹外发光、AI 紫蓝渐变、大面积渐变文字。
- 全站只有**一个**强调色（`#1F5FD0`）；语义色只用于状态表达，不做装饰。

---

## 2. 字体

| 用途 | 字族 | 字重可选 |
| --- | --- | --- |
| 中文 / 通用 | `Noto Sans SC`（回退：`system-ui, "PingFang SC", "Microsoft YaHei"`） | 400 Regular / 500 Medium / 600 SemiBold |
| 数字 / 参数值 / 匹配度 / 日期 / 编号 / 日志 | `Geist Mono`（回退：`"JetBrains Mono", ui-monospace`） | 400 / 500 Medium |

> **数字必须用等宽**：材料参数、匹配度百分比、价格、日期在多行/多列中要对齐，比例字体做不到。

### 2.1 字号梯度（原型实际使用值，共 8 级）

| 级别 | 字号 | 行高 | 字重 | 典型用途 |
| --- | --- | --- | --- | --- |
| Display | `20px` | `26px` | 600 | 页面主标题（「全部材料」） |
| H1 | `15px` | `20px` | 600 | 材料名（详情页）、面板标题 |
| H2 | `14px` | `19px` | 600 | 产品名、卡片大标题 |
| H3 | `13px` | `18px` | 600 / 400 | 卡片标题、消息正文、待选面板标题 |
| Body | `12px` | `17–19px` | 400 / 500 | 正文、按钮、表格单元格、输入值 |
| Small | `11px` | `15–18px` | 400 / 500 | 参数行、标签、表头、说明 |
| Caption | `10px` | `14–16px` | 400 / 500 | Chip 文字、计数、脚注 |
| Micro | `9px` | `12px` | 400 | 版本号等极弱信息 |

**行高取值集合**：`12 / 14 / 15 / 16 / 17 / 18 / 19 / 20 / 26`（px 整数，不用 em，避免中英混排抖动）。

---

## 3. 间距

基准单位 **4px**，只使用下列档位：

`2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 24 · 32`

| 场景 | 值 |
| --- | --- |
| 图标与文字 | 4 / 5 / 6 |
| Chip 之间、按钮之间 | 6 / 8 |
| 卡片内部元素之间 | 8 / 10 / 12 |
| 卡片之间、区块之间 | 16 / 18 |
| 页面内容内边距 | 24 |
| 面板内边距（顶栏/侧栏） | 16 |
| 卡片内边距 | 14（材料卡片）/ 16（内容卡）/ 18（大卡） |

**禁止**在实现中出现 `7px`、`13px`、`25px` 这类非档位值。

---

## 4. 圆角

| Token | 值 | 用途 |
| --- | --- | --- |
| `--radius-xs` | `4px` | 快捷键 Chip、滑杆 |
| `--radius-sm` | `5px` | 标签 Chip、徽章、分段控件内项 |
| `--radius-md` | `6px` | 图标按钮、小数 Chip、diff 色块 |
| `--radius-lg` | `7px` | 按钮、输入框、筛选项、Tab |
| `--radius-xl` | `8px` | 全局搜索框、提示条、次级信息块 |
| `--radius-2xl` | `10px` | 表格容器、待选卡片、导入落地区 |
| `--radius-3xl` | `12px` | 材料卡片、内容卡片 |
| `--radius-4xl` | `14px` | Modal |

---

## 5. 阴影与层次

| Token | 值 | 用途 |
| --- | --- | --- |
| `--shadow-none` | 无 | **默认**：卡片 / 面板一律用 `1px` 描边表达层次，不用阴影 |
| `--shadow-modal` | `0 18px 44px -6px rgba(15,20,28,0.24)` | 仅 Modal 使用（06 屏） |

> 这是本设计的**核心视觉决策**：工具型界面用「描边分层」而非「投影分层」，200 条材料滚动时不产生视觉噪音。除 Modal 外任何元素都不要加投影。

---

## 6. 可访问性（实测对比度）

| 前景 | 背景 | 对比度 | 结论 |
| --- | --- | --- | --- |
| `#15171C` | `#FFFFFF` | **17.9:1** | ✅ 远超 AA |
| `#3F4855` | `#FFFFFF` | **9.9:1** | ✅ |
| `#565E6B` | `#FFFFFF` | **6.5:1** | ✅ |
| `#1F5FD0` | `#FFFFFF` | **5.6:1** | ✅ 可用于 12px 文字 |
| `#1F5FD0` | `#EAEFFB` | **5.0:1** | ✅ 选中态文字达标 |
| `#A5322E` | `#FCECEB` | **6.6:1** | ✅ |
| `#1D6B47` | `#E7F5EE` | **5.7:1** | ✅ |
| `#8A5A12` | `#FDF3E4` | **5.9:1** | ✅ |
| `#8A93A1` | `#FFFFFF` | **3.1:1** | ⚠️ 仅限非关键信息 |
| `#AAB2BD` | `#FFFFFF` | **2.4:1** | ⚠️ 仅限占位符 |
| `#6B7482` | `#FFFFFF` | **4.7:1** | ✅ **浅灰信息文字的合规替代** |

**落地规则**
1. 任何 10–11px 的文本，若用户**必须读到才能做判断**（来源、时间、统计、失败原因），一律用 `#6B7482` 或 `--text-3`。
2. 占位符、单位后缀、"可选" 类标注可保留浅灰。
3. 焦点态统一样式：`outline: 2px solid #1F5FD0; outline-offset: 2px;`（**不可移除**，全站键盘可达）。
4. 交互热区最小 `32×32`；表格行内图标按钮 `26×26` + 行高 46，满足触控与误触要求。
5. 动效需支持 `prefers-reduced-motion: reduce`（回落为无过渡）。

---

## 7. AntD 5 主题覆盖值（可直接粘贴）

```ts
// theme.ts
import type { ThemeConfig } from 'antd'

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
      cellPaddingBlock: 14,        // → 行高 46
      borderColor: '#EFF1F4',
      fontSize: 12,
    },
    Modal: { borderRadiusLG: 14, contentBg: '#FFFFFF', titleFontSize: 15 },
    Button: { fontWeight: 500, primaryShadow: 'none', defaultShadow: 'none' },
    Input:  { paddingInline: 10, activeShadow: 'none' },
    Segmented: { itemSelectedBg: '#EAEFFB', itemSelectedColor: '#1F5FD0' },
    Slider: { trackBg: '#1F5FD0', railBg: '#EEF0F3', handleColor: '#FFFFFF', handleSize: 14, railSize: 8 },
    Tooltip: { colorBgSpotlight: '#15171C', borderRadius: 6, fontSize: 11 },
  },
}
```

---

## 8. 内容撰写规范（UI 文案）

| 类型 | 规范 | 正例 | 反例 |
| --- | --- | --- | --- |
| 按钮 | 动词开头，≤ 6 字 | `新建材料` `确认约束并生成推荐` | `确定` `提交` |
| 危险操作 | 明示后果 | `清空我的反馈` | `删除` |
| 空态 | 说明「为什么空」+「下一步做什么」 | 「从上方推荐结果点击『+ 加入待选』，把感兴趣的材料收进来」 | 「暂无数据」 |
| 降级提示 | 说明放宽了什么 | 「未识别到硬约束，请直接选择工艺和温度」 | 「解析失败」 |
| 免责 | 明确边界 | 「辅助选型，最终以实测验证为准」 | — |
| 数字 | 带单位且单位在标签里 | 标签 `耐温上限 °C` / 值 `150` | 值 `150°C` 混排 |

**禁止出现**：`Elevate` `Seamless` `Unleash` 之类的空话；占位符用「请输入」而不给示例。
全局搜索框的占位符必须是**真实可搜的例子**：`搜索材料名称 / 别名 / 牌号 / 应用场景，例如 PP、PA66+GF30、保险丝座`。
