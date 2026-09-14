# MatSelect · 汽车材料选型知识库

> 一期交付：**单机本地部署（单用户）的「材料选型决策辅助 / 个人选型工作台」**
> 依据：`doc/汽车材料库产品需求设计书_v0.2.md` + `doc/前端原型/`（10 屏定稿原型与规范）
> 形态：本地服务（FastAPI + SQLite）+ 浏览器 UI（React 18 + TS + Ant Design 5），无登录、无权限、无移动端

---

## 1. 快速开始

### 1.1 后端（FastAPI + SQLite）

```powershell
# 依赖已安装在隔离虚拟环境（如需重建）：
#   C:\Users\73937\.workbuddy\binaries\python\versions\3.13.12\python.exe -m venv C:\Users\73937\.workbuddy\binaries\python\envs\matselect
#   & C:\Users\73937\.workbuddy\binaries\python\envs\matselect\Scripts\python.exe -m pip install -r backend\requirements.txt

cd D:\Documents\MyDoc\CODE\MatSelect\backend
& C:\Users\73937\.workbuddy\binaries\python\envs\matselect\Scripts\python.exe run.py
```

- 服务地址：`http://127.0.0.1:8100`
- 交互式 API 文档：`http://127.0.0.1:8100/docs`
- 首次启动自动建表（`data/matselect.db`），若材料表为空则导入 `data/*.json` 种子数据

### 1.2 前端（Vite + React + AntD）

```powershell
cd D:\Documents\MyDoc\CODE\MatSelect\frontend
npm run dev      # 开发：http://127.0.0.1:5173（/api 已代理到 8100）
npm run build    # 生产构建：tsc --noEmit + vite build → dist/
```

### 1.3 一键自检

```powershell
& C:\Users\73937\.workbuddy\binaries\python\envs\matselect\Scripts\python.exe -m pytest backend\tests -v
```

---

## 2. 目录结构

```
MatSelect/
├── doc/                      来源文档（需求设计书 + 前端原型交付包）——只读
├── docs/
│   ├── plan/                 交付计划 / 架构设计 / 接口契约 / 数据字典
│   └── acceptance/           验收用例矩阵 / 缺陷与交付判定报告
├── data/                     种子数据（分类树 / 50 条材料 / 术语词典 / 材料包样例）
│   └── matselect.db          SQLite 单文件数据库（运行期生成，不入版本控制）
├── backend/
│   ├── run.py                启动入口
│   ├── app/
│   │   ├── main.py           应用装配 + 路由自动发现
│   │   ├── core/             配置 / 错误 / 日志
│   │   ├── db/               连接 / schema.sql / 建库与种子
│   │   ├── repository/       数据访问层（Repository 模式，SQL 只在这一层）
│   │   ├── services/         业务逻辑（推荐引擎 / 材料 / 任务 / 待选 / 回评 / 导出导入）
│   │   ├── schemas/          Pydantic 数据模型
│   │   └── api/              HTTP 路由（薄层）
│   ├── scripts/              种子导入与数据校验脚本
│   └── tests/                验收自动化测试
└── frontend/
    └── src/
        ├── styles/           Design Tokens（唯一色值来源）+ 共享 UI 基元
        ├── theme/            AntD 主题覆盖
        ├── icons/            线性图标集
        ├── layout/           TopBar / NavRail / SidePanel / AppShell
        ├── api/              接口客户端与 TS 类型
        ├── utils/            展示层格式化规则
        ├── pages/            10 屏页面
        ├── components/       可复用组件
        └── features/         复杂功能区
```

---

## 3. 核心约定

- **接口契约**：`docs/plan/02-接口契约与工程约定.md`（冻结）。API 路径、返回形状、字段名一经冻结不得擅改。
- **分支模型**：`main`（稳定）/ `dev`（集成）/ `feat|data|test|docs|fix/<模块>`；提交遵循 Conventional Commits。
- **视觉红线**：卡片圆角 12 / 控件 7 / Chip 5；除 Modal 外无投影；每屏唯一主按钮；数字等宽；1366×768 起无横向滚动。
- **数据安全**：数据即 `data/matselect.db` 单文件；每日自动备份副本至 `data/backups/`，并可用「导出材料包」做冷备份。
- **免责声明**：**辅助选型，最终以实测验证为准。**

---

## 4. 专家团

| 角色 | 代号 | 职责 |
| --- | --- | --- |
| 技术负责人 | team-lead | 契约冻结、集成、Git 提交与发布、冲突裁决 |
| 产品经理 | pm | 交付与迭代计划、职责矩阵、风险台账 |
| 系统架构师 | architect | 核心底座框架、数据模型、存储层抽象 |
| 产品数据收集师 | data-collector | 分类体系、术语词典、50 条材料建库 |
| 后端开发专家 | backend-dev | 后端业务逻辑、推荐引擎、导入导出 |
| 前端开发专家 | frontend-dev | 10 屏页面与 UI、四态、键盘可达 |
| 产品验收交付专家 | acceptance | 验收用例矩阵、端到端验证、交付判定 |

详见 `TEAM.md` 与 `docs/plan/00-交付与迭代计划.md`。
