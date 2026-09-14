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
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter

from app.core.config import API_HOST, API_PORT, APP_VERSION, PROJECT_ROOT, CORS_ORIGINS
from app.core.errors import ApiError
from app.db.connection import close_conn
from app.db import init_db as _init_db


def _register_routers(app: FastAPI) -> None:
    """从 app.api 包自动发现并挂载所有 router。失败则警告后跳过。"""
    try:
        import app.api as api_pkg
    except Exception as e:
        print(f"[main] 警告: 无法导入 app.api 包（{e}），跳过路由自动发现。")
        return
    try:
        for mod in pkgutil.iter_modules(api_pkg.__path__):
            mod_name = mod.name
            try:
                module = importlib.import_module(f"app.api.{mod_name}")
            except Exception as e:
                print(f"[main] 警告: 导入模块 app.api.{mod_name} 失败（{e}），已跳过。")
                continue
            router = getattr(module, "router", None)
            if isinstance(router, APIRouter):
                app.include_router(router, prefix="/api")
    except Exception as e:
        print(f"[main] 警告: 路由自动发现过程出错（{e}），部分路由可能未挂载。")


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

    # 前端产物存在则挂载（SPA 回退）。必须在 API 路由之后挂载。
    dist = PROJECT_ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")

    return app


app = create_app()
