# -*- coding: utf-8 -*-
"""
Prompt模板管理模块

管理PPT生成过程中使用的所有提示词模板，
包括系统提示词、大纲生成和内容生成的模板。
支持中英文双语场景。
"""

from __future__ import annotations

from typing import Optional


# ── 系统提示词 ────────────────────────────────────────────────────

SYSTEM_PROMPT: str = """你是一位专业的PPT内容策划师和演示文稿设计师。你擅长将复杂主题转化为结构清晰、内容精炼的演示文稿。

你的核心能力：
1. 深入理解主题，提炼核心观点
2. 设计逻辑清晰的演示结构
3. 撰写简洁有力的标题和要点
4. 确保内容的专业性和可读性

输出要求：
- 严格以JSON格式输出
- 内容精炼，每页要点不超过5条
- 标题简洁有力，控制在20字以内
- 要点描述清晰，每条控制在50字以内
- 确保内容准确、专业、有价值"""


# ── 大纲生成模板（两步生成 - 新版）────────────────────────────────

OUTLINE_PROMPT_TEMPLATE_V2: str = """请根据以下主题，设计一个{pages}页的PPT大纲。

主题：{prompt}

要求：
1. 生成3-5个一级章节（chapter），每个章节有明确的主题
2. 每个章节下包含2-4个二级标题（item），每个二级标题对应一页PPT内容
3. 每个二级标题下可包含2-3个要点（sub_items），作为内容提示
4. 逻辑清晰，层次分明，内容连贯
5. 总页数控制在{pages}页左右（包含封面和结尾）

请以JSON格式输出，结构如下：
```json
{{
  "title": "PPT主题名",
  "chapters": [
    {{
      "chapter_title": "第一章标题",
      "items": [
        {{"title": "二级标题1", "sub_items": ["要点1", "要点2"]}},
        {{"title": "二级标题2", "sub_items": ["要点1", "要点2"]}}
      ]
    }}
  ]
}}
```"""


# ── 内容生成模板（两步生成 - 单页内容）────────────────────────────

CONTENT_PROMPT_TEMPLATE_V2: str = """请为PPT生成一页详细内容。

PPT主题：{title}
所属章节：{chapter_title}
当前页面二级标题：{item_title}
内容要点提示：{sub_items}
PPT风格：{style_name}
字数要求：每页约{words}字

要求：
1. 标题简洁有力，控制在20字以内
2. 正文段落精炼，约{words}字左右，语言流畅专业
3. 要点列表清晰，3-5条，每条控制在50字以内
4. 内容紧扣主题，专业准确，有深度

请以JSON格式输出：
```json
{{
  "title": "页面标题",
  "body": "正文段落（{words}字左右）",
  "points": ["要点1", "要点2", "要点3"]
}}
```"""


# ── 封面页内容生成模板 ────────────────────────────────────────────

COVER_PROMPT_TEMPLATE: str = """请为PPT生成封面页内容。

主题：{prompt}
PPT风格：{style_name}

要求：
1. 主标题简洁有力，突出主题核心
2. 可以添加副标题或标语
3. 体现{style_name}风格的专业感

请以JSON格式输出：
```json
{{
  "title": "主标题",
  "body": "副标题或标语（可选）",
  "points": []
}}
```"""


# ── 结尾页内容生成模板 ────────────────────────────────────────────

ENDING_PROMPT_TEMPLATE: str = """请为PPT生成结尾页内容。

主题：{prompt}
PPT风格：{style_name}

要求：
1. 感谢语或总结性标题
2. 可以包含核心观点回顾
3. 简洁大方

请以JSON格式输出：
```json
{{
  "title": "感谢语或总结标题",
  "body": "总结性文字（可选）",
  "points": ["核心观点1", "核心观点2"]
}}
```"""



# ── 批量内容生成模板（优化：合并多页为一次调用）────────────────────

BATCH_CONTENT_PROMPT_TEMPLATE: str = """请为PPT批量生成所有内容页的详细内容。

PPT主题：{title}
PPT风格：{style_name}
字数要求：每页约{words}字

以下是需要生成内容的页面列表（共{page_count}页）：
{pages_desc}

要求：
1. 为每一页分别生成标题、正文和要点
2. 标题简洁有力，控制在20字以内
3. 正文段落精炼，约{words}字左右，语言流畅专业
4. 要点列表清晰，3-5条，每条控制在50字以内
5. 内容紧扣主题，专业准确，有深度
6. 各页之间逻辑连贯，内容不重复

请严格按照以下JSON数组格式输出，数组中每个元素对应一页内容：
```json
[
  {{{{
    "title": "第1页标题",
    "body": "第1页正文（{words}字左右）",
    "points": ["要点1", "要点2", "要点3"]
  }}}},
  {{{{
    "title": "第2页标题",
    "body": "第2页正文（{words}字左右）",
    "points": ["要点1", "要点2", "要点3"]
  }}}}
]
```
"""


# ── 旧版模板（保留兼容）───────────────────────────────────────────

OUTLINE_PROMPT_TEMPLATE: str = """请根据以下主题，设计一个{pages}页的PPT大纲。

主题：{prompt}

要求：
1. 第1页为封面页，包含主题标题
2. 中间页为内容页，每页聚焦一个子主题
3. 最后1页为结尾页，总结核心观点
4. 大纲要逻辑清晰，层次分明

请以JSON数组格式输出大纲，每个元素包含：
- "page": 页码
- "title": 该页标题
- "brief": 该页内容概要（一句话描述）

示例格式：
```json
[
  {{"page": 1, "title": "封面标题", "brief": "主题概述"}},
  {{"page": 2, "title": "子主题1", "brief": "该页概要"}},
  ...
]
```"""

CONTENT_PROMPT_TEMPLATE: str = """请为PPT的第{page_num}页生成详细内容。

主题：{prompt}
当前页标题：{page_title}
当前页概要：{page_brief}
PPT风格：{style_name}

要求：
1. 标题简洁有力，控制在20字以内
2. 正文内容精炼，如有正文请控制在100字以内
3. 要点列表清晰，每条控制在50字以内，不超过5条
4. 内容专业准确，语言流畅

请以JSON格式输出：
```json
{{
  "title": "页面标题",
  "body": "正文内容（可选，可为空字符串）",
  "points": ["要点1", "要点2", "要点3"]
}}
```"""


# ── 模板格式化函数 ─────────────────────────────────────────────────


def format_batch_content_prompt_v2(
    title: str,
    chapters: list,
    style_name: str,
    words: int = 150,
) -> str:
    """
    格式化批量内容生成提示词（优化版）。

    将所有内容页的prompt合并为一次批量调用，
    让AI一次性返回全部页面的JSON数组。

    Args:
        title: PPT主题标题
        chapters: 大纲章节列表
        style_name: 风格名称
        words: 每页字数要求

    Returns:
        str: 格式化后的完整批量提示词
    """
    page_descs = []
    page_idx = 1
    for chapter in chapters:
        for item in chapter.items:
            sub_items_str = "、".join(item.sub_items) if item.sub_items else "无"
            desc = (
                f"第{page_idx}页:\n"
                f"  - 所属章节: {chapter.chapter_title}\n"
                f"  - 页面标题: {item.title}\n"
                f"  - 内容要点提示: {sub_items_str}"
            )
            page_descs.append(desc)
            page_idx += 1

    pages_desc = "\n\n".join(page_descs)
    page_count = len(page_descs)

    return BATCH_CONTENT_PROMPT_TEMPLATE.format(
        title=title,
        style_name=style_name,
        words=words,
        page_count=page_count,
        pages_desc=pages_desc,
    )


def format_outline_prompt(prompt: str, pages: int) -> str:
    """
    格式化大纲生成提示词（旧版兼容）。

    Args:
        prompt: 用户输入的PPT主题描述
        pages: 期望的幻灯片页数

    Returns:
        str: 格式化后的完整提示词
    """
    return OUTLINE_PROMPT_TEMPLATE.format(
        prompt=prompt,
        pages=pages,
    )


def format_outline_prompt_v2(prompt: str, pages: int) -> str:
    """
    格式化大纲生成提示词（两步生成新版）。

    Args:
        prompt: 用户输入的PPT主题描述
        pages: 期望的幻灯片页数

    Returns:
        str: 格式化后的完整提示词
    """
    return OUTLINE_PROMPT_TEMPLATE_V2.format(
        prompt=prompt,
        pages=pages,
    )


def format_content_prompt(
    prompt: str,
    page_num: int,
    page_title: str,
    page_brief: str,
    style_name: str,
) -> str:
    """
    格式化单页内容生成提示词（旧版兼容）。

    Args:
        prompt: 用户输入的PPT主题描述
        page_num: 当前页码
        page_title: 当前页标题
        page_brief: 当前页概要
        style_name: 风格名称

    Returns:
        str: 格式化后的完整提示词
    """
    return CONTENT_PROMPT_TEMPLATE.format(
        prompt=prompt,
        page_num=page_num,
        page_title=page_title,
        page_brief=page_brief,
        style_name=style_name,
    )


def format_content_prompt_v2(
    title: str,
    chapter_title: str,
    item_title: str,
    sub_items: list[str],
    style_name: str,
    words: int = 150,
) -> str:
    """
    格式化单页内容生成提示词（两步生成新版）。

    Args:
        title: PPT主题标题
        chapter_title: 所属章节标题
        item_title: 当前页面二级标题
        sub_items: 内容要点提示列表
        style_name: 风格名称
        words: 每页字数要求

    Returns:
        str: 格式化后的完整提示词
    """
    sub_items_str = "、".join(sub_items) if sub_items else "无"
    return CONTENT_PROMPT_TEMPLATE_V2.format(
        title=title,
        chapter_title=chapter_title,
        item_title=item_title,
        sub_items=sub_items_str,
        style_name=style_name,
        words=words,
    )


def format_cover_prompt(prompt: str, style_name: str) -> str:
    """
    格式化封面页提示词。

    Args:
        prompt: 用户输入的PPT主题描述
        style_name: 风格名称

    Returns:
        str: 格式化后的完整提示词
    """
    return COVER_PROMPT_TEMPLATE.format(
        prompt=prompt,
        style_name=style_name,
    )


def format_ending_prompt(prompt: str, style_name: str) -> str:
    """
    格式化结尾页提示词。

    Args:
        prompt: 用户输入的PPT主题描述
        style_name: 风格名称

    Returns:
        str: 格式化后的完整提示词
    """
    return ENDING_PROMPT_TEMPLATE.format(
        prompt=prompt,
        style_name=style_name,
    )
