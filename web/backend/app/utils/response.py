"""
OpsBrain Web — Response Utilities

统一响应格式和异常处理
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import HTTPException
from fastapi.responses import JSONResponse


class ApiResponse:
    """统一 API 响应格式"""

    @staticmethod
    def success(data: Any = None, message: str = "操作成功") -> JSONResponse:
        return JSONResponse({
            "ok": True,
            "message": message,
            "data": data,
        })

    @staticmethod
    def error(message: str, code: int = 400) -> JSONResponse:
        return JSONResponse({
            "ok": False,
            "error": message,
        }, status_code=code)

    @staticmethod
    def not_found(message: str = "资源不存在") -> JSONResponse:
        return ApiResponse.error(message, 404)

    @staticmethod
    def unauthorized(message: str = "未授权") -> JSONResponse:
        return ApiResponse.error(message, 401)

    @staticmethod
    def forbidden(message: str = "禁止访问") -> JSONResponse:
        return ApiResponse.error(message, 403)


class AppException(HTTPException):
    """应用级异常"""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundException(AppException):
    """资源不存在异常"""

    def __init__(self, detail: str = "资源不存在"):
        super().__init__(detail=detail, status_code=404)


class UnauthorizedException(AppException):
    """未授权异常"""

    def __init__(self, detail: str = "未授权"):
        super().__init__(detail=detail, status_code=401)


class ForbiddenException(AppException):
    """禁止访问异常"""

    def __init__(self, detail: str = "禁止访问"):
        super().__init__(detail=detail, status_code=403)