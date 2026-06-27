# -*- coding: utf-8 -*-
"""
PPT内容生成服务模块

核心业务逻辑：使用 OpenAI 兼容 API 生成结构化PPT内容。
流程：用户prompt → AI生成大纲 → AI逐页生成内容 → 构建slides数据。

使用异步IO实现高性能并发调用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from openai import AsyncOpenAI

from app.config import Settings
from app.models import (
    ContentSlide,
    OutlineChapter,
    OutlineItem,
    Slide,
    SlideType,
)
from app.prompts import (
    SYSTEM_PROMPT,
    format_batch_content_prompt_v2,
    format_content_prompt,
    format_content_prompt_v2,
    format_cover_prompt,
    format_ending_prompt,
    format_outline_prompt,
    format_outline_prompt_v2,
)
from app.themes import ThemeConfig, get_theme

logger = logging.getLogger(__name__)


# ── 内部数据结构 ──────────────────────────────────────────────────


@dataclass
class OutlineItemLegacy:
    """旧版大纲条目数据结构。"""

    page: int
    title: str
    brief: str


@dataclass
class PageContent:
    """单页内容数据结构。"""

    title: str
    body: str
    points: list[str]


# ── JSON提取工具 ─────────────────────────────────────────────────


def extract_json_from_response(text: str) -> dict[str, Any] | list[Any]:
    """
    从AI响应文本中提取JSON内容。

    AI响应可能包含markdown代码块包裹的JSON，
    需要提取出纯JSON字符串再进行解析。

    Args:
        text: AI响应的原始文本

    Returns:
        解析后的JSON对象（字典或列表）

    Raises:
        ValueError: 当无法提取有效JSON时抛出
    """
    # 尝试直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 尝试从markdown代码块中提取
    patterns = [
        r"```json\s*\n?(.*?)\n?\s*```",  # ```json ... ```
        r"```\s*\n?(.*?)\n?\s*```",  # ``` ... ```
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # 最后尝试：找到第一个 [ 或 { 到最后一个 ] 或 }
    start_bracket = -1
    for i, char in enumerate(text):
        if char in ("[", "{"):
            start_bracket = i
            break

    if start_bracket >= 0:
        end_bracket = len(text)
        for i in range(len(text) - 1, start_bracket, -1):
            if text[i] in ("]", "}"):
                end_bracket = i + 1
                break
        try:
            return json.loads(text[start_bracket:end_bracket])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从AI响应中提取有效JSON内容。响应片段: {text[:200]}")


# ── 核心生成器类 ──────────────────────────────────────────────────


class PPTGenerator:
    """
    PPT内容生成器。

    负责协调AI API调用，完成从主题描述到结构化幻灯片数据的全流程生成。

    使用方式:
        generator = PPTGenerator(settings)
        slides = await generator.generate(prompt="AI趋势", pages=10, style="business")
    """

    def __init__(self, settings: Settings) -> None:
        """
        初始化PPT生成器。

        Args:
            settings: 应用配置实例
        """
        self._settings = settings
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """
        获取或创建OpenAI异步客户端（懒初始化）。

        Returns:
            AsyncOpenAI: 异步OpenAI客户端实例
        """
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._settings.openai_api_key,
                base_url=self._settings.openai_base_url,
                timeout=self._settings.openai_timeout,
            )
            logger.info(
                "OpenAI客户端已初始化，base_url=%s, model=%s",
                self._settings.openai_base_url,
                self._settings.openai_model,
            )
        return self._client

    async def _call_ai(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        调用AI API获取文本响应。

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选，默认使用PPT策划师提示词）

        Returns:
            str: AI响应的原始文本

        Raises:
            RuntimeError: 当API调用失败时抛出
        """
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            logger.debug("调用AI API，prompt长度=%d", len(user_prompt))
            response = await client.chat.completions.create(
                model=self._settings.openai_model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=self._settings.openai_max_tokens,
                temperature=self._settings.openai_temperature,
            )
            content = response.choices[0].message.content or ""
            logger.debug("AI响应长度=%d", len(content))
            return content
        except Exception as e:
            logger.error("AI API调用失败: %s", str(e))
            raise RuntimeError(f"AI API调用失败: {e}") from e

    # ── 两步生成：生成大纲 ────────────────────────────────────────

    async def generate_outline_v2(
        self,
        prompt: str,
        pages: int,
    ) -> tuple[str, list[OutlineChapter]]:
        """
        生成PPT大纲（两步生成新版）。

        调用AI根据主题和页数生成结构化大纲，
        包含一级章节、二级标题和要点提示。

        Args:
            prompt: PPT主题描述
            pages: 期望的幻灯片页数

        Returns:
            tuple[str, list[OutlineChapter]]: (PPT标题, 章节列表)

        Raises:
            RuntimeError: 当大纲生成失败时抛出
        """
        user_prompt = format_outline_prompt_v2(prompt, pages)
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            if not isinstance(data, dict):
                raise ValueError("大纲响应应为JSON对象")

            title = str(data.get("title", prompt))
            chapters_data = data.get("chapters", [])

            if not isinstance(chapters_data, list):
                raise ValueError("chapters字段应为JSON数组")

            chapters: list[OutlineChapter] = []
            for ch_data in chapters_data:
                chapter_title = str(ch_data.get("chapter_title", ""))
                items_data = ch_data.get("items", [])

                items: list[OutlineItem] = []
                if isinstance(items_data, list):
                    for it_data in items_data:
                        item_title = str(it_data.get("title", ""))
                        sub_items = list(it_data.get("sub_items", []))
                        items.append(
                            OutlineItem(
                                title=item_title,
                                sub_items=sub_items,
                            )
                        )

                chapters.append(
                    OutlineChapter(
                        chapter_title=chapter_title,
                        items=items,
                    )
                )

            logger.info("大纲生成完成，标题='%s'，共%d个章节", title, len(chapters))
            return title, chapters

        except (ValueError, KeyError, TypeError) as e:
            logger.error("大纲解析失败: %s, 原始响应: %s", str(e), raw_response[:500])
            raise RuntimeError(f"大纲生成失败，AI返回格式异常: {e}") from e

    # ── 两步生成：生成内容 ────────────────────────────────────────

    async def generate_content_v2(
        self,
        title: str,
        chapters: list[OutlineChapter],
        style: str,
        words_per_page: int = 150,
    ) -> list[ContentSlide]:
        """
        根据大纲生成完整PPT内容（两步生成新版 - 批量优化）。

        优化策略：
        - 封面和结尾页各一次独立调用（它们风格特殊）
        - 所有内容页合并为一次批量调用（大幅减少API调用次数）
        - 封面 + 批量内容 + 结尾 使用 asyncio.gather 并发（3个并发任务）

        Args:
            title: PPT主题标题
            chapters: 大纲章节列表
            style: 风格标识符
            words_per_page: 每页字数要求

        Returns:
            list[ContentSlide]: 内容幻灯片列表

        Raises:
            RuntimeError: 当内容生成失败时抛出
        """
        logger.info(
            "开始生成PPT内容(批量优化): title='%s', chapters=%d, style=%s",
            title[:50],
            len(chapters),
            style,
        )

        # 获取风格主题
        theme: ThemeConfig = get_theme(style)
        logger.info("使用风格主题: %s (%s)", theme.name, theme.key)

        # 收集所有内容页元信息
        content_metas: list[dict] = []
        for chapter in chapters:
            for item in chapter.items:
                content_metas.append({
                    "chapter_title": chapter.chapter_title,
                    "item_title": item.title,
                })

        # 使用 asyncio.gather 并发处理封面 + 批量内容 + 结尾（3个并发任务）
        cover_task = self._generate_cover(title, theme.name)
        ending_task = self._generate_ending(title, theme.name)
        batch_task = self._generate_batch_content(
            title=title,
            chapters=chapters,
            style_name=theme.name,
            words_per_page=words_per_page,
        )

        cover_result, batch_result, ending_result = await asyncio.gather(
            cover_task, batch_task, ending_task,
            return_exceptions=True,
        )

        slides: list[ContentSlide] = []
        slide_number = 1

        # 1. 封面页
        if isinstance(cover_result, Exception):
            logger.error("封面页生成异常: %s", str(cover_result))
            cover_content = PageContent(title=title, body="", points=[])
        else:
            cover_content = cover_result
        slides.append(
            ContentSlide(
                slide_number=slide_number,
                type=SlideType.COVER,
                chapter_title="",
                item_title="",
                title=cover_content.title,
                body=cover_content.body,
                points=cover_content.points,
                background=theme.background_gradient,
            )
        )
        slide_number += 1
        logger.info("封面页生成完成")

        # 2. 批量内容页
        if isinstance(batch_result, Exception):
            logger.error("批量内容生成异常: %s", str(batch_result))
            # 使用降级内容
            for meta in content_metas:
                slides.append(
                    ContentSlide(
                        slide_number=slide_number,
                        type=SlideType.CONTENT,
                        chapter_title=meta["chapter_title"],
                        item_title=meta["item_title"],
                        title=meta["item_title"],
                        body="",
                        points=["内容生成失败，请稍后重试"],
                        background=theme.background_gradient,
                    )
                )
                slide_number += 1
        else:
            batch_contents: list[PageContent] = batch_result
            for i, page_content in enumerate(batch_contents):
                if i < len(content_metas):
                    meta = content_metas[i]
                else:
                    meta = {"chapter_title": "", "item_title": ""}
                slides.append(
                    ContentSlide(
                        slide_number=slide_number,
                        type=SlideType.CONTENT,
                        chapter_title=meta["chapter_title"],
                        item_title=meta["item_title"],
                        title=page_content.title,
                        body=page_content.body,
                        points=page_content.points,
                        background=theme.background_gradient,
                    )
                )
                slide_number += 1
        logger.info("批量内容页生成完成，共%d页", len(content_metas))

        # 3. 结尾页
        if isinstance(ending_result, Exception):
            logger.error("结尾页生成异常: %s", str(ending_result))
            ending_content = PageContent(title="谢谢观看", body="", points=[])
        else:
            ending_content = ending_result
        slides.append(
            ContentSlide(
                slide_number=slide_number,
                type=SlideType.ENDING,
                chapter_title="",
                item_title="",
                title=ending_content.title,
                body=ending_content.body,
                points=ending_content.points,
                background=theme.background_gradient,
            )
        )
        logger.info("结尾页生成完成")

        # 重新编号
        for i, slide in enumerate(slides, start=1):
            slide.slide_number = i

        logger.info("PPT内容生成完成(批量优化)，共%d页幻灯片", len(slides))
        return slides

    async def _generate_batch_content(
        self,
        title: str,
        chapters: list[OutlineChapter],
        style_name: str,
        words_per_page: int,
    ) -> list[PageContent]:
        """
        批量生成所有内容页（一次AI调用）。

        将所有内容页的prompt合并为一次批量调用，
        让AI一次性返回全部页面的JSON数组。

        Args:
            title: PPT主题标题
            chapters: 大纲章节列表
            style_name: 风格名称
            words_per_page: 每页字数要求

        Returns:
            list[PageContent]: 所有内容页的数据列表

        Raises:
            RuntimeError: 当AI调用或解析失败时抛出
        """
        # 检查是否有内容页
        total_items = sum(len(ch.items) for ch in chapters)
        if total_items == 0:
            return []

        logger.info("批量生成%d个内容页（一次AI调用）", total_items)
        user_prompt = format_batch_content_prompt_v2(
            title=title,
            chapters=chapters,
            style_name=style_name,
            words=words_per_page,
        )
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            if not isinstance(data, list):
                raise ValueError("批量内容响应应为JSON数组")

            results: list[PageContent] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                results.append(
                    PageContent(
                        title=str(item.get("title", "")),
                        body=str(item.get("body", "")),
                        points=list(item.get("points", [])),
                    )
                )

            logger.info("批量内容解析完成，共%d页", len(results))
            return results

        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                "批量内容解析失败: %s, 原始响应前500字符: %s",
                str(e),
                raw_response[:500],
            )
            # 返回基于大纲的降级内容
            fallback: list[PageContent] = []
            for chapter in chapters:
                for item in chapter.items:
                    fallback.append(
                        PageContent(
                            title=item.title,
                            body="",
                            points=item.sub_items if item.sub_items else [],
                        )
                    )
            return fallback

    async def _generate_content_page(
        self,
        title: str,
        chapter_title: str,
        item: OutlineItem,
        style_name: str,
        words_per_page: int,
    ) -> PageContent:
        """
        生成单个内容页。

        Args:
            title: PPT主题标题
            chapter_title: 所属章节标题
            item: 大纲条目
            style_name: 风格名称
            words_per_page: 每页字数要求

        Returns:
            PageContent: 页面内容数据
        """
        user_prompt = format_content_prompt_v2(
            title=title,
            chapter_title=chapter_title,
            item_title=item.title,
            sub_items=item.sub_items,
            style_name=style_name,
            words=words_per_page,
        )
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            if not isinstance(data, dict):
                raise ValueError("页面内容响应应为JSON对象")

            return PageContent(
                title=str(data.get("title", item.title)),
                body=str(data.get("body", "")),
                points=list(data.get("points", [])),
            )
        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                "内容页解析失败 [%s/%s]: %s", chapter_title, item.title, str(e)
            )
            # 返回基于大纲的降级内容
            return PageContent(
                title=item.title,
                body="",
                points=item.sub_items if item.sub_items else [],
            )

    async def _generate_cover(self, prompt: str, style_name: str) -> PageContent:
        """生成封面页内容。"""
        user_prompt = format_cover_prompt(prompt, style_name)
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            return PageContent(
                title=str(data.get("title", prompt)),
                body=str(data.get("body", "")),
                points=list(data.get("points", [])),
            )
        except (ValueError, KeyError, TypeError):
            return PageContent(title=prompt, body="", points=[])

    async def _generate_ending(self, prompt: str, style_name: str) -> PageContent:
        """生成结尾页内容。"""
        user_prompt = format_ending_prompt(prompt, style_name)
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            return PageContent(
                title=str(data.get("title", "谢谢观看")),
                body=str(data.get("body", "")),
                points=list(data.get("points", [])),
            )
        except (ValueError, KeyError, TypeError):
            return PageContent(title="谢谢观看", body="", points=[])

    # ── 旧版方法（保留兼容）───────────────────────────────────────

    async def generate_outline(
        self,
        prompt: str,
        pages: int,
    ) -> list[OutlineItemLegacy]:
        """
        生成PPT大纲（旧版兼容）。

        调用AI根据主题和页数生成结构化大纲。

        Args:
            prompt: PPT主题描述
            pages: 期望的幻灯片页数

        Returns:
            list[OutlineItemLegacy]: 大纲条目列表

        Raises:
            RuntimeError: 当大纲生成失败时抛出
        """
        user_prompt = format_outline_prompt(prompt, pages)
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            if not isinstance(data, list):
                raise ValueError("大纲响应应为JSON数组")

            outline: list[OutlineItemLegacy] = []
            for item in data:
                outline.append(
                    OutlineItemLegacy(
                        page=int(item.get("page", 0)),
                        title=str(item.get("title", "")),
                        brief=str(item.get("brief", "")),
                    )
                )

            # 按页码排序
            outline.sort(key=lambda x: x.page)
            logger.info("大纲生成完成，共%d页", len(outline))
            return outline

        except (ValueError, KeyError, TypeError) as e:
            logger.error("大纲解析失败: %s, 原始响应: %s", str(e), raw_response[:500])
            raise RuntimeError(f"大纲生成失败，AI返回格式异常: {e}") from e

    async def generate_page_content(
        self,
        prompt: str,
        page_num: int,
        page_title: str,
        page_brief: str,
        style_name: str,
    ) -> PageContent:
        """
        生成单页PPT内容（旧版兼容）。

        Args:
            prompt: PPT主题描述
            page_num: 当前页码
            page_title: 当前页标题
            page_brief: 当前页概要
            style_name: 风格名称

        Returns:
            PageContent: 页面内容数据

        Raises:
            RuntimeError: 当内容生成失败时抛出
        """
        user_prompt = format_content_prompt(
            prompt, page_num, page_title, page_brief, style_name
        )
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            if not isinstance(data, dict):
                raise ValueError("页面内容响应应为JSON对象")

            return PageContent(
                title=str(data.get("title", page_title)),
                body=str(data.get("body", "")),
                points=list(data.get("points", [])),
            )
        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                "第%d页内容解析失败: %s", page_num, str(e)
            )
            # 返回基于大纲的降级内容
            return PageContent(
                title=page_title,
                body=page_brief,
                points=[],
            )

    async def generate_cover(
        self,
        prompt: str,
        style_name: str,
    ) -> PageContent:
        """
        生成封面页内容（旧版兼容）。

        Args:
            prompt: PPT主题描述
            style_name: 风格名称

        Returns:
            PageContent: 封面页内容数据
        """
        user_prompt = format_cover_prompt(prompt, style_name)
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            return PageContent(
                title=str(data.get("title", prompt)),
                body=str(data.get("body", "")),
                points=list(data.get("points", [])),
            )
        except (ValueError, KeyError, TypeError):
            return PageContent(title=prompt, body="", points=[])

    async def generate_ending(
        self,
        prompt: str,
        style_name: str,
    ) -> PageContent:
        """
        生成结尾页内容（旧版兼容）。

        Args:
            prompt: PPT主题描述
            style_name: 风格名称

        Returns:
            PageContent: 结尾页内容数据
        """
        user_prompt = format_ending_prompt(prompt, style_name)
        raw_response = await self._call_ai(user_prompt, SYSTEM_PROMPT)

        try:
            data = extract_json_from_response(raw_response)
            return PageContent(
                title=str(data.get("title", "谢谢观看")),
                body=str(data.get("body", "")),
                points=list(data.get("points", [])),
            )
        except (ValueError, KeyError, TypeError):
            return PageContent(title="谢谢观看", body="", points=[])

    async def generate(
        self,
        prompt: str,
        pages: int,
        style: str,
    ) -> list[Slide]:
        """
        生成完整的PPT幻灯片数据（旧版一键生成）。

        完整流程：
        1. 获取风格主题配置
        2. 生成封面页内容
        3. 生成PPT大纲
        4. 并发生成各内容页
        5. 生成结尾页内容
        6. 组装为slides数组

        Args:
            prompt: PPT主题描述
            pages: 期望的幻灯片页数
            style: 风格标识符

        Returns:
            list[Slide]: 结构化的幻灯片数据数组

        Raises:
            RuntimeError: 当生成过程中出现不可恢复的错误时抛出
        """
        logger.info(
            "开始生成PPT: prompt='%s', pages=%d, style=%s",
            prompt[:50],
            pages,
            style,
        )

        # 1. 获取风格主题
        theme: ThemeConfig = get_theme(style)
        logger.info("使用风格主题: %s (%s)", theme.name, theme.key)

        # 2. 生成封面页
        cover_content = await self.generate_cover(prompt, theme.name)
        slides: list[Slide] = [
            Slide(
                slide_number=1,
                type=SlideType.COVER,
                title=cover_content.title,
                body=cover_content.body,
                points=cover_content.points,
                background=theme.background_gradient,
            )
        ]
        logger.info("封面页生成完成")

        # 3. 生成大纲（中间内容页）
        content_pages = pages - 2  # 减去封面和结尾
        if content_pages < 1:
            content_pages = 1

        outline = await self.generate_outline(prompt, content_pages)
        logger.info("大纲生成完成，共%d个内容页", len(outline))

        # 4. 并发生成各内容页
        async def _gen_content(item: OutlineItemLegacy) -> Slide:
            """生成单个内容页的幻灯片。"""
            content = await self.generate_page_content(
                prompt=prompt,
                page_num=item.page,
                page_title=item.title,
                page_brief=item.brief,
                style_name=theme.name,
            )
            return Slide(
                slide_number=item.page + 1,  # +1 因为第1页是封面
                type=SlideType.CONTENT,
                title=content.title,
                body=content.body,
                points=content.points,
                background=theme.background_gradient,
            )

        content_tasks = [_gen_content(item) for item in outline]
        content_slides = await asyncio.gather(*content_tasks, return_exceptions=True)

        for i, result in enumerate(content_slides):
            if isinstance(result, Exception):
                logger.error("第%d页内容生成异常: %s", i + 2, str(result))
                # 使用降级内容
                fallback = outline[i] if i < len(outline) else None
                if fallback:
                    slides.append(
                        Slide(
                            slide_number=i + 2,
                            type=SlideType.CONTENT,
                            title=fallback.title,
                            body=fallback.brief,
                            points=[],
                            background=theme.background_gradient,
                        )
                    )
            else:
                slides.append(result)

        # 5. 生成结尾页
        ending_content = await self.generate_ending(prompt, theme.name)
        slides.append(
            Slide(
                slide_number=len(slides) + 1,
                type=SlideType.ENDING,
                title=ending_content.title,
                body=ending_content.body,
                points=ending_content.points,
                background=theme.background_gradient,
            )
        )
        logger.info("结尾页生成完成")

        # 6. 按页码重新排序
        slides.sort(key=lambda s: s.slide_number)

        logger.info("PPT生成完成，共%d页幻灯片", len(slides))
        return slides

    async def close(self) -> None:
        """关闭OpenAI客户端连接。"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("OpenAI客户端已关闭")
