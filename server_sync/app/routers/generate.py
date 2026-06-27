# -*- coding: utf-8 -*-
"""
API路由模块 - PPT生成与健康检查

定义所有API端点，包括请求验证、错误处理和响应构建。
支持一键生成（旧版兼容）和两步生成（新版）。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import Settings, get_settings
from app.models import (
    ContentSlide,
    ErrorResponse,
    ExportHTMLRequest,
    GenerateContentRequest,
    GenerateContentResponse,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    OutlineChapter,
)
from app.services.ppt_generator import PPTGenerator

logger = logging.getLogger(__name__)

# ── 路由器实例 ────────────────────────────────────────────────────

router = APIRouter(prefix="/api", tags=["SlideForge API"])

# ── 生成器实例缓存 ────────────────────────────────────────────────

_generator: Optional[PPTGenerator] = None


def _get_generator(settings: Settings = Depends(get_settings)) -> PPTGenerator:
    """
    获取PPT生成器实例（依赖注入）。

    使用模块级缓存，避免重复创建客户端。

    Args:
        settings: 应用配置（通过FastAPI依赖注入）

    Returns:
        PPTGenerator: PPT生成器实例
    """
    global _generator
    if _generator is None:
        _generator = PPTGenerator(settings)
    return _generator


# ── API端点 ────────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="检查服务运行状态和版本信息",
    responses={
        200: {"description": "服务正常"},
    },
)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """
    健康检查端点。

    返回服务状态和版本信息，用于负载均衡器和监控系统的健康探测。

    Args:
        settings: 应用配置

    Returns:
        HealthResponse: 包含状态和版本信息的响应
    """
    return HealthResponse(
        status="ok",
        version=settings.app_version,
    )


# ── 两步生成：生成大纲 ────────────────────────────────────────────


@router.post(
    "/generate_outline",
    response_model=GenerateOutlineResponse,
    summary="生成PPT大纲",
    description="根据主题、页数和风格生成结构化PPT大纲（两步生成第一步）",
    responses={
        200: {"description": "大纲生成成功"},
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务内部错误"},
        503: {"model": ErrorResponse, "description": "AI服务不可用"},
    },
)
async def generate_outline(
    request: Request,
    body: GenerateOutlineRequest,
    settings: Settings = Depends(get_settings),
    generator: PPTGenerator = Depends(_get_generator),
) -> GenerateOutlineResponse:
    """
    生成PPT大纲端点（两步生成第一步）。

    接收用户输入的主题、页数和风格，调用AI生成结构化的大纲数据，
    包含一级章节、二级标题和要点提示。

    Args:
        request: FastAPI请求对象（用于日志记录）
        body: 生成大纲请求参数
        settings: 应用配置
        generator: PPT生成器实例

    Returns:
        GenerateOutlineResponse: 包含大纲数据的响应

    Raises:
        HTTPException: 当生成失败时返回对应的HTTP错误
    """
    start_time = time.monotonic()

    # ── 前置检查 ──────────────────────────────────────────────────
    if not settings.is_api_key_configured:
        logger.error("OpenAI API密钥未配置")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "detail": "AI服务未配置，请设置OPENAI_API_KEY环境变量",
            },
        )

    # ── 生成大纲 ──────────────────────────────────────────────────
    logger.info(
        "收到大纲生成请求: prompt='%s', pages=%d, style=%s, client=%s",
        body.prompt[:50],
        body.pages,
        body.style.value,
        request.client.host if request.client else "unknown",
    )

    try:
        title, chapters = await generator.generate_outline_v2(
            prompt=body.prompt,
            pages=body.pages,
        )
    except ValueError as e:
        logger.warning("请求参数错误: %s", str(e))
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "detail": str(e)},
        ) from None
    except RuntimeError as e:
        logger.error("大纲生成失败: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": "generation_failed", "detail": str(e)},
        ) from None
    except Exception as e:
        logger.exception("大纲生成过程中发生未预期错误")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "detail": "服务内部错误，请稍后重试"},
        ) from None

    # ── 构建响应 ──────────────────────────────────────────────────
    elapsed = time.monotonic() - start_time
    total_items = sum(len(ch.items) for ch in chapters)
    logger.info(
        "大纲生成完成: 标题='%s', %d个章节, %d个条目, 耗时%.2f秒",
        title,
        len(chapters),
        total_items,
        elapsed,
    )

    return GenerateOutlineResponse(
        title=title,
        chapters=chapters,
        total_pages=body.pages,
        style=body.style.value,
    )


# ── 两步生成：生成内容 ────────────────────────────────────────────


@router.post(
    "/generate_content",
    response_model=GenerateContentResponse,
    summary="生成PPT内容",
    description="根据大纲生成完整PPT内容（两步生成第二步）",
    responses={
        200: {"description": "内容生成成功"},
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务内部错误"},
        503: {"model": ErrorResponse, "description": "AI服务不可用"},
    },
)
async def generate_content(
    request: Request,
    body: GenerateContentRequest,
    settings: Settings = Depends(get_settings),
    generator: PPTGenerator = Depends(_get_generator),
) -> GenerateContentResponse:
    """
    生成PPT内容端点（两步生成第二步）。

    接收用户确认后的大纲数据，调用AI为每个二级标题生成详细页面内容，
    包含封面页、内容页和结尾页。

    Args:
        request: FastAPI请求对象（用于日志记录）
        body: 生成内容请求参数
        settings: 应用配置
        generator: PPT生成器实例

    Returns:
        GenerateContentResponse: 包含完整幻灯片内容的响应

    Raises:
        HTTPException: 当生成失败时返回对应的HTTP错误
    """
    start_time = time.monotonic()

    # ── 前置检查 ──────────────────────────────────────────────────
    if not settings.is_api_key_configured:
        logger.error("OpenAI API密钥未配置")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "detail": "AI服务未配置，请设置OPENAI_API_KEY环境变量",
            },
        )

    # ── 参数校验 ──────────────────────────────────────────────────
    if not body.chapters:
        logger.warning("内容生成请求中chapters为空")
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "detail": "chapters不能为空"},
        )

    # ── 生成内容 ──────────────────────────────────────────────────
    logger.info(
        "收到内容生成请求: title='%s', chapters=%d, style=%s, words=%d, client=%s",
        body.title[:50],
        len(body.chapters),
        body.style.value,
        body.words_per_page,
        request.client.host if request.client else "unknown",
    )

    try:
        slides = await generator.generate_content_v2(
            title=body.title,
            chapters=body.chapters,
            style=body.style.value,
            words_per_page=body.words_per_page,
        )
    except ValueError as e:
        logger.warning("请求参数错误: %s", str(e))
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "detail": str(e)},
        ) from None
    except RuntimeError as e:
        logger.error("内容生成失败: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": "generation_failed", "detail": str(e)},
        ) from None
    except Exception as e:
        logger.exception("内容生成过程中发生未预期错误")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "detail": "服务内部错误，请稍后重试"},
        ) from None

    # ── 构建响应 ──────────────────────────────────────────────────
    elapsed = time.monotonic() - start_time
    logger.info(
        "内容生成完成: 共%d页, 耗时%.2f秒",
        len(slides),
        elapsed,
    )

    return GenerateContentResponse(
        slides=slides,
        total_pages=len(slides),
        style=body.style.value,
        title=body.title,
    )


# ── 一键生成（旧版兼容）───────────────────────────────────────────


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="一键生成PPT",
    description="根据主题、页数和风格一键生成完整PPT幻灯片数据（兼容旧版）",
    responses={
        200: {"description": "PPT生成成功"},
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务内部错误"},
        503: {"model": ErrorResponse, "description": "AI服务不可用"},
    },
)
async def generate_ppt(
    request: Request,
    body: GenerateRequest,
    settings: Settings = Depends(get_settings),
    generator: PPTGenerator = Depends(_get_generator),
) -> GenerateResponse:
    """
    PPT一键生成端点（旧版兼容）。

    接收用户输入的主题、页数和风格，调用AI生成结构化的幻灯片数据。
    生成过程为异步IO，不会阻塞事件循环。

    Args:
        request: FastAPI请求对象（用于日志记录）
        body: 生成请求参数
        settings: 应用配置
        generator: PPT生成器实例

    Returns:
        GenerateResponse: 包含幻灯片数据的响应

    Raises:
        HTTPException: 当生成失败时返回对应的HTTP错误
    """
    start_time = time.monotonic()

    # ── 前置检查 ──────────────────────────────────────────────────
    if not settings.is_api_key_configured:
        logger.error("OpenAI API密钥未配置")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "detail": "AI服务未配置，请设置OPENAI_API_KEY环境变量",
            },
        )

    # ── 生成PPT ──────────────────────────────────────────────────
    logger.info(
        "收到PPT生成请求: prompt='%s', pages=%d, style=%s, client=%s",
        body.prompt[:50],
        body.pages,
        body.style.value,
        request.client.host if request.client else "unknown",
    )

    try:
        slides = await generator.generate(
            prompt=body.prompt,
            pages=body.pages,
            style=body.style.value,
        )
    except ValueError as e:
        logger.warning("请求参数错误: %s", str(e))
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "detail": str(e)},
        ) from None
    except RuntimeError as e:
        logger.error("PPT生成失败: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": "generation_failed", "detail": str(e)},
        ) from None
    except Exception as e:
        logger.exception("PPT生成过程中发生未预期错误")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "detail": "服务内部错误，请稍后重试"},
        ) from None

    # ── 构建响应 ──────────────────────────────────────────────────
    elapsed = time.monotonic() - start_time
    logger.info(
        "PPT生成完成: 共%d页, 耗时%.2f秒",
        len(slides),
        elapsed,
    )

    return GenerateResponse(
        slides=slides,
        total_pages=len(slides),
        style=body.style.value,
    )


# ── HTML导出端点 ──────────────────────────────────────────────────

_HTML_TEMPLATE: str = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
            background: #0a1529;
            color: #1a1a2e;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            overflow-x: hidden;
        }}
        .slide-container {{
            width: 1280px;
            max-width: 100vw;
            margin: 0 auto;
        }}
        .slide {{
            width: 100%;
            height: 720px;
            display: none;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 60px 80px;
            position: relative;
            overflow: hidden;
            animation: fadeIn 0.5s ease;
        }}
        .slide.active {{
            display: flex;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        /* 封面页 */
        .slide-cover {{
            background: linear-gradient(135deg, #102A54 0%, #0d1f40 40%, #162d5a 100%);
            color: #ffffff;
        }}
        .slide-cover .cover-title {{
            font-size: 48px;
            font-weight: 700;
            text-align: center;
            margin-bottom: 30px;
            letter-spacing: 2px;
            color: #ffffff;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}
        .slide-cover .cover-body {{
            font-size: 20px;
            color: #00B4D8;
            text-align: center;
            font-weight: 300;
            letter-spacing: 1px;
        }}
        .slide-cover .cover-line {{
            width: 80px;
            height: 3px;
            background: #FF7A1A;
            margin: 20px auto;
            border-radius: 2px;
        }}
        /* 内容页 */
        .slide-content {{
            background: linear-gradient(180deg, #f0f4f8 0%, #e8eef4 100%);
            justify-content: flex-start;
            padding-top: 80px;
        }}
        .slide-content .content-header {{
            width: 100%;
            margin-bottom: 30px;
            border-left: 4px solid #00B4D8;
            padding-left: 20px;
        }}
        .slide-content .content-header .chapter-label {{
            font-size: 13px;
            color: #00B4D8;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 6px;
        }}
        .slide-content .content-header .page-title {{
            font-size: 32px;
            font-weight: 700;
            color: #102A54;
        }}
        .slide-content .content-body {{
            width: 100%;
            font-size: 17px;
            line-height: 1.8;
            color: #3a3a4a;
            margin-bottom: 25px;
            background: #ffffff;
            padding: 30px 35px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        }}
        .slide-content .content-points {{
            width: 100%;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }}
        .slide-content .point-card {{
            flex: 1 1 calc(50% - 15px);
            min-width: 280px;
            background: #ffffff;
            border-radius: 10px;
            padding: 20px 25px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.05);
            border-left: 3px solid #00B4D8;
            font-size: 15px;
            color: #2a2a3a;
            line-height: 1.6;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .slide-content .point-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 24px rgba(0,0,0,0.1);
            border-left-color: #FF7A1A;
        }}
        /* 结尾页 */
        .slide-ending {{
            background: linear-gradient(135deg, #102A54 0%, #0d1f40 40%, #162d5a 100%);
            color: #ffffff;
        }}
        .slide-ending .ending-title {{
            font-size: 44px;
            font-weight: 700;
            text-align: center;
            margin-bottom: 25px;
            color: #ffffff;
        }}
        .slide-ending .ending-body {{
            font-size: 18px;
            color: #00B4D8;
            text-align: center;
            margin-bottom: 15px;
            font-weight: 300;
        }}
        .slide-ending .ending-points {{
            display: flex;
            gap: 30px;
            margin-top: 20px;
        }}
        .slide-ending .ending-point {{
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(0,180,216,0.3);
            border-radius: 8px;
            padding: 16px 28px;
            font-size: 15px;
            color: #c8d6e5;
            text-align: center;
        }}
        /* 导航 */
        .nav-bar {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(16,42,84,0.95);
            backdrop-filter: blur(10px);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            padding: 14px 30px;
            z-index: 1000;
            border-top: 1px solid rgba(0,180,216,0.2);
        }}
        .nav-btn {{
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #ffffff;
            font-size: 15px;
            padding: 8px 22px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            letter-spacing: 1px;
        }}
        .nav-btn:hover {{
            background: #00B4D8;
            border-color: #00B4D8;
            color: #ffffff;
        }}
        .nav-btn:disabled {{
            opacity: 0.35;
            cursor: not-allowed;
        }}
        .nav-btn:disabled:hover {{
            background: rgba(255,255,255,0.1);
            border-color: rgba(255,255,255,0.2);
        }}
        .nav-info {{
            color: #00B4D8;
            font-size: 14px;
            letter-spacing: 1px;
            min-width: 80px;
            text-align: center;
        }}
        .nav-brand {{
            color: rgba(255,255,255,0.5);
            font-size: 12px;
            letter-spacing: 1px;
            position: absolute;
            right: 30px;
        }}
        .page-footer {{
            position: absolute;
            bottom: 20px;
            right: 40px;
            font-size: 11px;
            color: rgba(0,0,0,0.25);
            letter-spacing: 1px;
        }}
        .slide-cover .page-footer,
        .slide-ending .page-footer {{
            color: rgba(255,255,255,0.3);
        }}
        /* 响应式 */
        @media (max-width: 1280px) {{
            .slide {{ height: auto; min-height: 100vh; padding: 40px 30px; }}
            .slide-content {{ padding-top: 40px; }}
        }}
    </style>
</head>
<body>
    <div class="slide-container">
        {slides_html}
    </div>
    <div class="nav-bar">
        <button class="nav-btn" id="prevBtn" onclick="navigate(-1)">&larr; 上一页</button>
        <span class="nav-info" id="pageInfo"></span>
        <button class="nav-btn" id="nextBtn" onclick="navigate(1)">下一页 &rarr;</button>
        <span class="nav-brand">Jeffrey_AI_step_1st</span>
    </div>
    <script>
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        const totalSlides = slides.length;

        function showSlide(index) {{
            slides.forEach((s, i) => s.classList.toggle('active', i === index));
            document.getElementById('prevBtn').disabled = index === 0;
            document.getElementById('nextBtn').disabled = index === totalSlides - 1;
            document.getElementById('pageInfo').textContent = (index + 1) + ' / ' + totalSlides;
        }}

        function navigate(delta) {{
            const next = currentSlide + delta;
            if (next >= 0 && next < totalSlides) {{
                currentSlide = next;
                showSlide(currentSlide);
            }}
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {{ navigate(-1); }}
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {{ e.preventDefault(); navigate(1); }}
        }});

        showSlide(0);
    </script>
</body>
</html>"""

_SLIDE_HTML_COVER: str = """<div class="slide slide-cover active">
    <div class="cover-line"></div>
    <h1 class="cover-title">{title}</h1>
    {body_html}
    <div class="cover-line"></div>
    <div class="page-footer">Jeffrey_AI_step_1st</div>
</div>"""

_SLIDE_HTML_CONTENT: str = """<div class="slide slide-content">
    <div class="content-header">
        {chapter_html}
        <h2 class="page-title">{title}</h2>
    </div>
    {body_html}
    {points_html}
    <div class="page-footer">Jeffrey_AI_step_1st</div>
</div>"""

_SLIDE_HTML_ENDING: str = """<div class="slide slide-ending">
    <h1 class="ending-title">{title}</h1>
    {body_html}
    {points_html}
    <div class="page-footer">Jeffrey_AI_step_1st</div>
</div>"""


def _build_slides_html(slides: list) -> str:
    """构建幻灯片HTML片段"""
    html_parts = []
    for i, slide in enumerate(slides):
        # 判断幻灯片类型
        slide_type = getattr(slide, 'type', None)
        type_val = str(slide_type.value) if hasattr(slide_type, 'value') else str(slide_type)
        title = getattr(slide, 'title', '') or ''
        body = getattr(slide, 'body', '') or ''
        points = getattr(slide, 'points', []) or []
        chapter_title = getattr(slide, 'chapter_title', '') or ''

        # 构建body HTML
        body_html = f'<p class="cover-body">{body}</p>' if body else ''

        if type_val == 'cover':
            slide_html = _SLIDE_HTML_COVER.format(
                title=title,
                body_html=body_html,
            )
        elif type_val == 'ending':
            points_html = ''
            if points:
                points_items = ''.join(
                    f'<span class="ending-point">{p}</span>' for p in points
                )
                points_html = f'<div class="ending-points">{points_items}</div>'
            if body:
                body_html = f'<p class="ending-body">{body}</p>'
            slide_html = _SLIDE_HTML_ENDING.format(
                title=title,
                body_html=body_html,
                points_html=points_html,
            )
        else:
            # 内容页
            chapter_html = ''
            if chapter_title:
                chapter_html = f'<div class="chapter-label">{chapter_title}</div>'
            if body:
                body_html = f'<div class="content-body">{body}</div>'
            else:
                body_html = ''
            points_html = ''
            if points:
                points_items = ''.join(
                    f'<div class="point-card">{p}</div>' for p in points
                )
                points_html = f'<div class="content-points">{points_items}</div>'
            slide_html = _SLIDE_HTML_CONTENT.format(
                chapter_html=chapter_html,
                title=title,
                body_html=body_html,
                points_html=points_html,
            )

        # 只有第一页保持 active
        if i > 0:
            slide_html = slide_html.replace(' active', '', 1)
        html_parts.append(slide_html)

    return '\n'.join(html_parts)


@router.post(
    "/export_html",
    response_class=HTMLResponse,
    summary="导出HTML幻灯片",
    description="接收幻灯片数据，返回符合Jeffrey设计规范的完整HTML文件",
    responses={
        200: {
            "description": "HTML文件生成成功",
            "content": {"text/html": {}},
        },
        400: {"model": ErrorResponse, "description": "请求参数错误"},
    },
)
async def export_html(
    body: ExportHTMLRequest,
) -> HTMLResponse:
    """
    HTML导出端点。

    接收包含 title、slides 和 style 的请求，
    生成符合 Jeffrey 设计规范的完整HTML幻灯片文件。

    设计规范：
    - 深蓝主色 #102A54
    - 青色装饰 #00B4D8
    - 橙色点缀 #FF7A1A
    - 幻灯片布局 1280×720px
    - 支持键盘翻页导航（← → 键）
    - 底部导航条
    - 页脚带 "Jeffrey_AI_step_1st" 品牌标识

    Args:
        body: 导出HTML请求参数

    Returns:
        HTMLResponse: 完整的HTML文件响应
    """
    if not body.slides:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "detail": "slides不能为空"},
        )

    slides_html = _build_slides_html(body.slides)
    full_html = _HTML_TEMPLATE.format(
        title=body.title,
        slides_html=slides_html,
    )

    logger.info(
        "HTML导出完成: title='%s', slides=%d, style=%s",
        body.title[:50],
        len(body.slides),
        body.style,
    )

    return HTMLResponse(content=full_html, status_code=200)

