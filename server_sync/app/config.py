# -*- coding: utf-8 -*-
"""
配置管理模块

使用 pydantic-settings 从环境变量读取应用配置，
支持 .env 文件和环境变量的双重加载方式。
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用全局配置类。

    所有配置项均可通过环境变量或 .env 文件进行覆盖。
    环境变量名称与字段名一致，不区分大小写。

    Attributes:
        app_name: 应用名称
        app_version: 应用版本号
        app_host: 服务监听地址
        app_port: 服务监听端口
        debug: 调试模式开关
        openai_api_key: OpenAI API 密钥
        openai_base_url: OpenAI API 基础URL（兼容第三方服务）
        openai_model: 使用的模型名称
        openai_max_tokens: 单次请求最大token数
        openai_temperature: 生成温度（0-2之间）
        openai_timeout: API请求超时时间（秒）
        cors_origins: 允许跨域的源列表（逗号分隔）
        log_level: 日志级别
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 应用基础配置 ──────────────────────────────────────────────
    app_name: str = Field(default="SlideForge API", description="应用名称")
    app_version: str = Field(default="1.0.0", description="应用版本号")
    app_host: str = Field(default="0.0.0.0", description="服务监听地址")
    app_port: int = Field(default=8000, description="服务监听端口")
    debug: bool = Field(default=False, description="调试模式开关")

    # ── OpenAI API 配置 ───────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API 密钥")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API 基础URL，支持自定义兼容接口",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="使用的模型名称",
    )
    openai_max_tokens: int = Field(
        default=4096,
        ge=256,
        le=16384,
        description="单次请求最大token数",
    )
    openai_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="生成温度，值越高输出越随机",
    )
    openai_timeout: float = Field(
        default=60.0,
        ge=5.0,
        le=300.0,
        description="API请求超时时间（秒）",
    )

    # ── CORS 跨域配置 ─────────────────────────────────────────────
    cors_origins: str = Field(
        default="*",
        description="允许跨域的源列表，多个源用逗号分隔，* 表示允许所有",
    )

    # ── 日志配置 ───────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志级别",
    )

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        """将逗号分隔的字符串解析为列表。"""
        if v == "*":
            return ["*"]
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        """获取解析后的CORS源列表。"""
        # cors_origins 经 field_validator 后已是 list 类型
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        return self.parse_cors_origins(self.cors_origins)

    @property
    def is_api_key_configured(self) -> bool:
        """检查API密钥是否已配置。"""
        return bool(self.openai_api_key and self.openai_api_key != "your-api-key-here")


# ── 全局配置单例 ──────────────────────────────────────────────────
def get_settings() -> Settings:
    """
    获取全局配置单例。

    Returns:
        Settings: 应用配置实例
    """
    return Settings()
