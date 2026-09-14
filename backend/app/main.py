# -*- coding: utf-8 -*-
"""应用装配：create_app() 负责中间件、路由自动发现、异常处理、生命周期、静态资源挂载。

路由自动发现：
- 遍历 app/api/ 下所有模块，取名为 router 的 APIRouter，挂到 prefix="/api"
- app/api 不存在 或 某模块导入失败 => 打印警告后继续，绝不导致应用崩溃
"""
import importlib
import pkgutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter

from app.core.config import API_HOST, API_PORT, APP_VERSION, PROJECT_ROOT, CORS_ORIGINS
from app.core.errors import ApiError
from app.db.connection import close_conn
from app.db import init_db as _init_db


# 显式路由模块清单（自动发现的**兜底**）。
# 必要性：PyInstaller 打包后 Python 模块位于归档中，`pkgutil.iter_modules(app.api.__path__)`
# 往往枚举不到任何模块，会导致**应用启动后 0 条业务路由**（接口全 404）。
# 因此自动发现失败或结果为 0 时，按本清单逐个 importlib 导入。
ROUTER_MODULES = (
    "materials", "categories", "recommend", "tasks", "shortlist",
    "feedback", "insights", "data_io", "settings", "system",
)


def _mount_module(app: FastAPI, mod_name: str) -> bool:
    """导入 app.api.<mod_name> 并挂载其 router；成功返回 True。"""
    try:
        module = importlib.import_module(f"app.api.{mod_name}")
    except Exception as e:  # noqa: BLE001
        print(f"[main] 警告: 导入模块 app.api.{mod_name} 失败（{e}），已跳过。")
        return False
    router = getattr(module, "router", None)
    if isinstance(router, APIRouter):
        app.include_router(router, prefix="/api")
        return True
    print(f"[main] 警告: app.api.{mod_name} 未暴露 router，已跳过。")
    return False


def _register_routers(app: FastAPI) -> None:
    """挂载所有业务 router：优先自动发现，失败则按显式清单兜底。"""
    mounted = 0

    try:
        import app.api as api_pkg

        for mod in pkgutil.iter_modules(api_pkg.__path__):
            if mod.name.startswith("_") or mod.name == "routes":
                continue
            if _mount_module(app, mod.name):
                mounted += 1
    except Exception as e:  # noqa: BLE001
        print(f"[main] 警告: 路由自动发现失败（{e}）。")

    if mounted == 0:
        print("[main] 自动发现未挂载任何 router（打包运行常见），改用显式清单兜底。")
        for mod_name in ROUTER_MODULES:
            if _mount_module(app, mod_name):
                mounted += 1

    print(f"[main] 已挂载 {mounted} 个 router（前缀 /api）。")


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "VALIDATION_ERROR", "message": "参数校验失败"}},
        )

    @app.exception_handler(Exception)
    async def handle_generic(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL", "message": "服务器内部错误"}},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表 + 种子
    _init_db.init_db()
    _init_db.seed_if_empty()
    yield
    # 关闭时释放连接
    close_conn()


def _mount_spa(app: FastAPI) -> None:
    """挂载前端产物并实现 SPA history 回退。

    为什么不能只用 `StaticFiles(html=True)`：它只对目录请求返回 index.html，
    对未知路径一律 404。而前端用 `createBrowserRouter`（HTML5 history），
    任何深链或浏览器刷新（如 /materials、/tasks/1、/settings）都会 404。

    约定：
    - `/assets/*` 交给 StaticFiles（带缓存语义的构建产物）
    - 其余未知路径回退到 index.html，把路由交给前端
    - **`/api/*` 未命中不回退**，仍返回统一错误体（否则前端会把 200 的 HTML 当接口响应）
    """
    dist = PROJECT_ROOT / "frontend" / "dist"
    if not dist.exists():
        print("[main] 未找到 frontend/dist，跳过 SPA 挂载（仅提供 API）。")
        return

    index = dist / "index.html"
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise ApiError("NOT_FOUND", "接口不存在", 404)
        target = dist / full_path
        if full_path and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(index))


def create_app() -> FastAPI:
    # ⚠️ lifespan 必须显式传入：否则启动/关闭钩子不会执行，
    # 全新安装会因「未建表」在第一个请求时报 `no such table: material`。
    app = FastAPI(title="MatSelect", version=APP_VERSION, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_routers(app)
    _register_exception_handlers(app)

    # 静态资源与 SPA 回退必须在 API 路由之后挂载，避免抢路由。
    _mount_spa(app)

    return app


app = create_app()
