# -*- coding: utf-8 -*-
"""
PPT风格主题配置模块

定义三种PPT风格的配色方案和视觉属性，
每种风格包含完整的颜色体系、字体建议和背景描述。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ThemeConfig:
    """
    PPT风格主题配置。

    Attributes:
        name: 风格名称（中文）
        key: 风格标识符
        primary_color: 主色调（深色，用于标题和重要元素）
        secondary_color: 辅助色（中等色，用于副标题和边框）
        light_color: 浅色（用于背景和装饰元素）
        accent_color: 强调色（用于高亮和按钮）
        background_gradient: 背景渐变描述
        title_font: 推荐标题字体
        body_font: 推荐正文字体
        description: 风格描述
    """

    name: str
    key: str
    primary_color: str
    secondary_color: str
    light_color: str
    accent_color: str
    background_gradient: str
    title_font: str
    body_font: str
    description: str
    extra_colors: dict[str, str] = field(default_factory=dict)


# ── 预定义风格主题 ────────────────────────────────────────────────

BUSINESS_THEME = ThemeConfig(
    name="商务蓝",
    key="business",
    primary_color="#1a365d",
    secondary_color="#2b6cb0",
    light_color="#bee3f8",
    accent_color="#3182ce",
    background_gradient="linear-gradient(135deg, #1a365d 0%, #2b6cb0 50%, #bee3f8 100%)",
    title_font="'Microsoft YaHei', 'PingFang SC', 'Helvetica Neue', sans-serif",
    body_font="'Microsoft YaHei', 'PingFang SC', 'Helvetica Neue', sans-serif",
    description="专业稳重的商务风格，适合企业汇报、商业提案等正式场合",
    extra_colors={
        "text_light": "#ffffff",
        "text_dark": "#1a202c",
        "border": "#2b6cb0",
        "card_bg": "rgba(255, 255, 255, 0.1)",
        "shadow": "rgba(26, 54, 93, 0.3)",
    },
)

TECH_THEME = ThemeConfig(
    name="科技青",
    key="tech",
    primary_color="#0d4f4f",
    secondary_color="#38b2ac",
    light_color="#81e6d9",
    accent_color="#4fd1c5",
    background_gradient="linear-gradient(135deg, #0d4f4f 0%, #38b2ac 50%, #81e6d9 100%)",
    title_font="'Microsoft YaHei', 'PingFang SC', 'Segoe UI', sans-serif",
    body_font="'Microsoft YaHei', 'PingFang SC', 'Segoe UI', sans-serif",
    description="现代科技感风格，适合技术分享、产品发布、科技主题演讲",
    extra_colors={
        "text_light": "#ffffff",
        "text_dark": "#1a202c",
        "border": "#38b2ac",
        "card_bg": "rgba(255, 255, 255, 0.08)",
        "shadow": "rgba(13, 79, 79, 0.3)",
    },
)

CREATIVE_THEME = ThemeConfig(
    name="活力橙粉",
    key="creative",
    primary_color="#c05621",
    secondary_color="#ed8936",
    light_color="#feb2b2",
    accent_color="#f6ad55",
    background_gradient="linear-gradient(135deg, #c05621 0%, #ed8936 50%, #feb2b2 100%)",
    title_font="'Microsoft YaHei', 'PingFang SC', 'Arial', sans-serif",
    body_font="'Microsoft YaHei', 'PingFang SC', 'Arial', sans-serif",
    description="充满活力的创意风格，适合创意展示、教育培训、营销活动",
    extra_colors={
        "text_light": "#ffffff",
        "text_dark": "#1a202c",
        "border": "#ed8936",
        "card_bg": "rgba(255, 255, 255, 0.12)",
        "shadow": "rgba(192, 86, 33, 0.3)",
    },
)

# ── 风格注册表 ─────────────────────────────────────────────────────

THEME_REGISTRY: dict[str, ThemeConfig] = {
    BUSINESS_THEME.key: BUSINESS_THEME,
    TECH_THEME.key: TECH_THEME,
    CREATIVE_THEME.key: CREATIVE_THEME,
}


def get_theme(style_key: str) -> ThemeConfig:
    """
    根据风格标识获取主题配置。

    Args:
        style_key: 风格标识符（business/tech/creative）

    Returns:
        ThemeConfig: 对应的主题配置

    Raises:
        ValueError: 当风格标识不存在时抛出
    """
    theme = THEME_REGISTRY.get(style_key)
    if theme is None:
        available = ", ".join(THEME_REGISTRY.keys())
        raise ValueError(
            f"未知的风格 '{style_key}'，可选值：{available}"
        )
    return theme


def get_all_themes() -> dict[str, ThemeConfig]:
    """
    获取所有可用的风格主题。

    Returns:
        dict: 风格标识到主题配置的映射字典
    """
    return THEME_REGISTRY.copy()
