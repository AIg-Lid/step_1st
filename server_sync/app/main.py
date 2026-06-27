# -*- coding: utf-8 -*-
"""
SlideForge API 主应用模块

创建和配置FastAPI应用实例，包括：
- CORS中间件（支持前端跨域访问）
- 请求日志中间件
- 统一错误处理
- API路由注册
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.models import ErrorResponse
from app.routers.generate import router as generate_router
from app.routers.export_routes import router as export_router
from app.routers.agent_routes import router as agent_router

# ── 日志配置 ──────────────────────────────────────────────────────

logger = logging.getLogger("slideforge")


def _setup_logging(settings: Settings) -> None:
    """
    配置应用日志。

    Args:
        settings: 应用配置实例
    """
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── 中间件 ────────────────────────────────────────────────────────


async def _request_logging_middleware(request: Request, call_next) -> JSONResponse:
    """
    请求日志中间件。

    记录每个HTTP请求的方法、路径、状态码和耗时。

    Args:
        request: 请求对象
        call_next: 下一个中间件/路由处理函数

    Returns:
        JSONResponse: 响应对象
    """
    start_time = time.monotonic()
    method = request.method
    path = request.url.path

    # 跳过健康检查的详细日志
    if path == "/api/health" and method == "GET":
        response = await call_next(request)
        return response

    logger.info(">>> %s %s", method, path)

    response = await call_next(request)

    elapsed = time.monotonic() - start_time
    logger.info(
        "<<< %s %s -> %d (%.3fs)",
        method,
        path,
        response.status_code,
        elapsed,
    )

    return response


# ── 异常处理器 ────────────────────────────────────────────────────


def _create_validation_error_handler(app: FastAPI) -> None:
    """
    注册请求参数验证错误处理器。

    Args:
        app: FastAPI应用实例
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """处理请求参数验证失败。"""
        errors = exc.errors()
        detail_messages = [
            f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg', '')}"
            for err in errors
        ]
        logger.warning(
            "请求验证失败 %s %s: %s",
            request.method,
            request.url.path,
            detail_messages,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="validation_error",
                detail="; ".join(detail_messages),
            ).model_dump(),
        )


def _create_generic_error_handler(app: FastAPI) -> None:
    """
    注册通用异常处理器。

    Args:
        app: FastAPI应用实例
    """

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """处理所有未捕获的异常。"""
        logger.exception(
            "未处理的异常 %s %s: %s",
            request.method,
            request.url.path,
            str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="internal_error",
                detail="服务内部错误，请稍后重试",
            ).model_dump(),
        )


# ── 应用工厂 ──────────────────────────────────────────────────────


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """
    创建并配置FastAPI应用实例。

    Args:
        settings: 应用配置（可选，默认从环境变量加载）

    Returns:
        FastAPI: 配置完成的应用实例
    """
    if settings is None:
        settings = get_settings()

    # 初始化日志
    _setup_logging(settings)

    # 创建应用
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI驱动的PPT幻灯片生成API服务",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # ── 注册中间件 ────────────────────────────────────────────────

    # CORS跨域中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求日志中间件
    app.middleware("http")(_request_logging_middleware)

    # ── 注册异常处理器 ───────────────────────────────────────────
    _create_validation_error_handler(app)
    _create_generic_error_handler(app)

    # ── 注册路由 ─────────────────────────────────────────────────
    app.include_router(generate_router)
    app.include_router(export_router)
    app.include_router(agent_router)

    logger.info(
        "SlideForge API 已启动，版本=%s, debug=%s",
        settings.app_version,
        settings.debug,
    )

    return app


# ── 模块级应用实例（供 uvicorn 加载） ──────────────────────────────
app = create_app()
