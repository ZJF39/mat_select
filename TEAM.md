# TEAM.md · MatSelect 专家团协作手册

> 团队形态：Windows 单机本地部署、单用户、无鉴权的「汽车材料选型知识库 MatSelect」一期项目。
> 协作以「冻结契约」为唯一接口准绳，详见 `docs/plan/02-接口契约与工程约定.md`。
> 本文件由 PM 维护；变更须团队 lead 批准。

---

## 1. 专家团花名册

| 角色（中文） | 代号（Agent） | 一句话职责 |
| --- | --- | --- |
| 团队负责人 | team-lead | 统筹排期、裁决阻塞、跨角色协调与最终交付 |
| 产品经理 | pm | 范围/排期/开放问题裁决/风险台账；产出 `00-交付与迭代计划.md` 与 `TEAM.md` |
| 系统架构师 | architect | 应用骨架、DB schema 与初始化、连接/事务/错误/日志基础设施、Repository 基类 |
| 技术负责人 | tech-lead | 技术栈与构建配置、前端底座/Token/主题、API 类型契约、全局布局；持有冻结契约 02 |
| 产品数据收集师 | data-collector | 材料/分类/术语原始数据与种子脚本，保障首批 ≥50 条且完整率 >90% |
| 后端开发专家 | backend-dev | 业务 Repository / API / 推荐·任务·回评·导入服务 / Pydantic 模型 |
| 前端开发专家 | frontend-dev | 10 屏页面、16 组件、特性模块、React Query/Zustand 状态接入 |
| 产品验收交付专家 | acceptance | 验收用例、自动化测试、性能/四态/键盘核查、交付与盲区报告 |

---

## 2. 协作协议

### 2.1 交接规范
- 每个里程碑末 `dev` → `main` 合入并打 tag（M0→`v0.1.0-m0` … M5→`v1.0.0`），见 `00-交付与迭代计划.md §3/§5.3`。
- 交接以「可验证交付物 + Definition of Done」为准，下游角色在依赖项 DoD 达成后才能启动（见 §3 文件归属与依赖）。
- 交接发现对方文件未达 DoD：通过 SendMessage 通知对方角色 + team-lead，不自行补改他人文件。

### 2.2 报障碍规范
- 阻塞/分歧/风险一律用 SendMessage 上报对应角色并抄 team-lead；PM 维护风险台账（00 §7）。
- 契约与 PRD 出现分歧：**以冻结契约为准**，不擅自改契约；需调整时由 tech-lead 批准并全队同步。
- 硬依赖未就绪（如 schema 未定、types 未出）时，下游用 mock/占位先行，但须在依赖达成后替换并自测。

### 2.3 契约变更流程
1. 提议方在 `docs/plan/02` 提变更请求（含理由/影响面/返工范围），SendMessage 给 tech-lead + team-lead。
2. tech-lead 评估并裁决；若批准，修订契约并显式标注版本，全队同步。
3. 关联角色据此更新各自文件；PM 同步更新 `00-交付与迭代计划.md` 的依赖/风险。

### 2.4 沟通约束
- 跨角色协调走 SendMessage（同事直发），团队级事项 broadcast，最终结论回报 team-lead。
- 禁止在 `main` 直接提交；每位专家只提交自己「拥有」路径（见 §3）。

---

## 3. 文件归属速查表（直接引用契约 §2 目录树）

```
MatSelect/
├── doc/                                  # 来源文档（只读，禁止修改）
├── docs/
│   ├── plan/00-交付与迭代计划.md          # [PM]
│   ├── plan/01-架构设计.md                # [架构师]
│   ├── plan/02-接口契约与工程约定.md       # [技术负责人·冻结]
│   └── acceptance/**                      # [验收专家]
├── data/                                  # [数据收集师]
│   ├── categories.json  term_alias.json  materials.json  material_pack_sample.json
├── backend/
│   ├── requirements.txt                   # [技术负责人]
│   ├── run.py                             # [架构师]
│   ├── app/
│   │   ├── main.py                        # [架构师] 应用装配 + 路由自动发现
│   │   ├── core/**                        # [架构师] config / responses / errors / logging
│   │   ├── db/**                          # [架构师] connection.py / schema.sql / init_db.py
│   │   ├── repository/base.py             # [架构师] BaseRepository + 连接/事务/Row 工具
│   │   ├── repository/*.py（除 base）      # [后端专家]
│   │   ├── api/**                         # [后端专家] 每个模块一个 router
│   │   ├── services/**                    # [后端专家]
│   │   └── schemas/**                     # [后端专家] Pydantic 模型
│   ├── scripts/seed_data.py               # [数据收集师]
│   └── tests/**                           # [验收专家]
└── frontend/
    ├── package.json  vite.config.ts  tsconfig*.json  index.html   # [技术负责人]
    └── src/
        ├── main.tsx  App.tsx  router.tsx         # [技术负责人]
        ├── styles/tokens.css                     # [技术负责人]（源自 doc/前端原型/tokens）
        ├── theme/**  api/client.ts  api/types.ts # [技术负责人]
        ├── layout/**                             # [技术负责人] TopBar/NavRail/SidePanel/AppShell
        ├── pages/**  components/**  features/**  # [前端专家]
```

> 归属冲突仲裁：以契约 §2 为唯一准绳；新增文件须落入对应角色目录，禁止在他人目录新建。需要他人文件变更时，一律 SendMessage 通知 team-lead / tech-lead。

---

*文档结束 · 维护者 PM · 与 `docs/plan/00-交付与迭代计划.md` 配套使用*
