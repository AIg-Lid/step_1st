# -*- coding: utf-8 -*-
"""
SlideForge API 项目入口

启动uvicorn ASGI服务器运行FastAPI应用。
支持命令行直接运行: python run.py
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from app.config import get_settings
from app.main import create_app

logger = logging.getLogger("slideforge")


def main() -> None:
    """
    应用启动入口函数。

    从环境变量加载配置，创建FastAPI应用，启动uvicorn服务器。
    """
    settings = get_settings()
    app = create_app(settings)

    logger.info("正在启动服务器 %s:%d ...", settings.app_host, settings.app_port)

    uvicorn.run(
        app=app,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
        access_log=False,  # 使用自定义日志中间件替代
    )


if __name__ == "__main__":
    main()
