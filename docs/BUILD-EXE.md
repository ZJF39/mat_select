# 打包为 Windows exe（PyInstaller）

## 1. 一键构建

```powershell
cd D:\Documents\MyDoc\CODE\MatSelect
$PY = "C:\Users\73937\.workbuddy\binaries\python\envs\matselect\Scripts\python.exe"

# ① 先构建前端（打包会把 frontend/dist 整体塞进 exe）
cd frontend
node node_modules\typescript\bin\tsc --noEmit
node node_modules\vite\bin\vite.js build
cd ..

# ② 打包后端（单文件）
& $PY -m PyInstaller --noconfirm --clean --onefile --console `
  --name MatSelect --distpath release --workpath build_pyi --specpath build_pyi `
  --paths backend `
  --add-data "frontend/dist;frontend/dist" `
  --add-data "backend/app/db/schema.sql;app/db" `
  --add-data "data/categories.json;data" `
  --add-data "data/materials.json;data" `
  --add-data "data/term_alias.json;data" `
  --add-data "data/material_pack_sample.json;data" `
  --exclude-module tkinter --exclude-module matplotlib `
  --hidden-import openpyxl --hidden-import multipart `
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.http.h11_impl --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.lifespan.on `
  --hidden-import app.api.materials --hidden-import app.api.categories `
  --hidden-import app.api.recommend --hidden-import app.api.tasks `
  --hidden-import app.api.shortlist --hidden-import app.api.feedback `
  --hidden-import app.api.insights --hidden-import app.api.data_io `
  --hidden-import app.api.settings --hidden-import app.api.system `
  launcher.py
```

产物：`release\MatSelect.exe`（单文件）。

## 1.1 另一个 exe：材料包工具（配合提示词包使用）

给最终用户在大模型产出 JSON 后转成可导入材料包用。**用户无需安装 Python。**

```powershell
& $PY -m PyInstaller --noconfirm --clean --onefile --console `
  --name MatSelectPackTool `
  --distpath release --workpath build_pyi --specpath build_pyi `
  --paths backend `
  --hidden-import app.services.io_service `
  --exclude-module tkinter --exclude-module matplotlib `
  tools\make_pack.py
```

产物：`release\MatSelectPackTool.exe`（**15.8 MB**）。

> 注意：`make_pack.py` 里对 `app.services.io_service` 的导入是**函数内延迟导入**，
> PyInstaller 静态分析看不到，**必须**显式 `--hidden-import app.services.io_service`，
> 否则运行时会报 `无法加载后端校验和算法`。

用法：把 JSON 文件**拖到 exe 上**，或
`MatSelectPackTool.exe 输入.json -o 输出.json [--check] [--no-pause]`。
打包态下结束会等待回车（避免双击时窗口一闪而过）；脚本调用请加 `--no-pause`。

## 2. 使用方式

双击 `MatSelect.exe` 即可：控制台显示访问地址，并自动打开浏览器。
也可指定端口或不自动开浏览器：

```powershell
.\release\MatSelect.exe --port 8200 --no-browser
```

停止：在控制台窗口按 `Ctrl+C`，或直接关闭窗口。

## 3. 运行时目录约定（重要）

exe 是「程序 + 只读资源」的封装；**可写数据不写在 exe 内**，而是放在 exe 同级的 `data\`：

| 路径 | 内容 | 说明 |
| --- | --- | --- |
| `<exe 同级>\data\matselect.db` | SQLite 数据库 | 首次启动自动建表并导入种子；**这就是全部数据** |
| `<exe 同级>\data\matselect.db-wal` / `-shm` | WAL 日志（SQLite 自动维护） | `journal_mode=WAL` 下，**未 checkpoint 的新数据可能只在 `-wal` 里** |
| `<exe 同级>\data\backups\` | 自动/手动备份 | 设置页「立即备份」写入此处 |
| `<exe 同级>\data\*.json` | 种子数据（可选） | 放同名文件可覆盖出厂种子；不放则用 exe 内置种子 |
| exe 内部（`_MEIPASS`） | `frontend/dist`、`schema.sql`、出厂种子 | **只读**，退出即清理 |

因此：**把 exe 单独拷到任意目录都能运行**，首次运行会在该目录生成 `data\`。

> ⚠️ **备份正确姿势（WAL 模式下的常见坑）**
> 不要只拷 `matselect.db` 一个文件 —— WAL 模式下最新写入可能还在 `matselect.db-wal` 中，
> 单拷主库会**丢掉最近的修改**。正确做法二选一：
> 1. **推荐**：用设置页的「立即备份」（后端走 SQLite 在线备份 API，生成 WAL 一致快照，落在 `data\backups\`）；
> 2. 或**先退出程序**再整体复制 `data\` 整个目录。

## 4. 打包相关代码改动（源码运行行为不变）

| 文件 | 改动 | 原因 |
| --- | --- | --- |
| `backend/app/core/config.py` | 新增 `FROZEN` / `BUNDLE_DIR` / `APP_DIR` / `SEED_DIR`；`DATA_DIR` 在打包时指向 exe 同级 `data\` | onefile 的 `_MEIPASS` 退出即清理，不能把数据库写在里面 |
| `backend/app/db/init_db.py` | `_load_json()` 按「可写数据目录 → 只读种子目录」顺序查找 | 打包后出厂种子在 `_MEIPASS\data`，而不在可写目录 |
| `backend/app/main.py` | 路由注册增加**显式模块清单兜底**（`ROUTER_MODULES`） | 打包后模块在归档中，`pkgutil.iter_modules` 枚举不到 → 会导致 0 条路由（接口全 404） |

非打包运行时 `BUNDLE_DIR == APP_DIR == 项目根`，上述分支不生效，行为与打包前完全一致。

## 5. 已知限制

- 单文件产物实测 **17.4 MB**（`release\MatSelect.exe`）。
- 单文件模式首次启动需解包到临时目录，冷启动比 `--onedir` 慢 1~3 秒。
- 控制台窗口无法隐藏为该工具的「托盘应用」；如需无窗口运行，可改 `--console` 为 `--windowed`，但会失去日志与 `Ctrl+C` 停止能力（不建议）。
- 未做代码签名，Windows SmartScreen 首次运行可能提示「未知发布者」。
- 杀软可能对 PyInstaller 单文件产物误报（自解包行为），如遇拦截需加白名单。