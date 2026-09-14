"""统一错误模型（契约 §3.1）。

所有业务错误统一抛 ApiError，由 main.py 的异常处理中间件转换为
HTTP 4xx/5xx + body {"error": {"code": ..., "message": ...}}。
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """业务错误基类。code 为机器码，message 为中文可读文案。"""

    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def not_found(msg: str = "资源不存在") -> ApiError:
    return ApiError("NOT_FOUND", msg, 404)


def validation_error(msg: str = "参数校验失败") -> ApiError:
    return ApiError("VALIDATION_ERROR", msg, 400)


def conflict(msg: str = "资源冲突，操作被拒绝") -> ApiError:
    return ApiError("CONFLICT", msg, 409)


def import_rejected(msg: str = "导入校验未通过") -> ApiError:
    return ApiError("IMPORT_REJECTED", msg, 422)


def internal(msg: str = "服务器内部错误") -> ApiError:
    return ApiError("INTERNAL", msg, 500)


def register_exception_handlers(app) -> None:
    """将 ApiError 统一转换为契约错误体。"""

    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(HTTPException)
    async def _handle_http(request: Request, exc: HTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "VALIDATION_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail)}},
        )
