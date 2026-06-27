# -*- coding: utf-8 -*-
"""
AI 文档助手路由 — AgentScope 2.0 + DeepSeek
支持结构化 JSON actions：Agent 直接操作 PPT/DOCX/XLSX
"""

from __future__ import annotations

import logging, time, json, re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agentscope.agent import Agent
from agentscope.model import DeepSeekChatModel
from agentscope.credential import DeepSeekCredential
from agentscope.message import Msg
from agentscope.message._base import TextBlock

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Agent API"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    tab: str = Field(default="")
    title: str = Field(default="")
    context: str = Field(default="")
    history: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    tab: str
    actions: list[dict] = Field(default_factory=list)  # 结构化动作指令


# ═══════════════════════════════════════════════════
# System Prompt — 含完整动作指令规范
# ═══════════════════════════════════════════════════

SYSTEM_PROMPT = """你是 Jeffrey_AI_step_1st 平台的 AI 文档助手，名字"Jeffrey 助手"。

你有能力直接修改用户的文档！当用户要求修改 PPT/Word/Excel 时，你必须遵守以下规则：

## ACTIONS 动作指令格式

在回复的最后，用 ```json 代码块包裹动作指令（如果有的话）。格式如下：

```json
{"actions": [...]}
```

每个 action 必须具备 type 和 对应的参数。

### PPT 动作类型

| type | 说明 | 参数 |
|------|------|------|
| update_outline_title | 修改大纲标题 | {"title": "新标题"} |
| update_chapter_title | 修改章节标题 | {"chapterIndex": N, "title": "新标题"} |
| update_item_title | 修改要点标题 | {"chapterIndex": N, "itemIndex": N, "title": "新标题"} |
| update_sub_item | 修改子要点 | {"chapterIndex": N, "itemIndex": N, "subIndex": N, "text": "新内容"} |
| add_chapter | 添加章节 | {"title": "章节标题", "items": [{"title":"要点1","subs":["子要点"]}]} 或 {"afterIndex": N, "title": "..."} |
| add_item | 添加要点 | {"chapterIndex": N, "title": "要点标题", "subs": ["子1","子2"]} 或 {"afterIndex": N, ...} |
| add_point | 添加子要点 | {"chapterIndex": N, "itemIndex": N, "text": "子要点内容"} |
| remove_chapter | 删除章节 | {"chapterIndex": N} |
| remove_item | 删除要点 | {"chapterIndex": N, "itemIndex": N} |
| remove_point | 删除子要点 | {"chapterIndex": N, "itemIndex": N, "subIndex": N} |

### DOCX 动作类型

| type | 说明 | 参数 |
|------|------|------|
| insert_text | 在文档末尾追加文本 | {"text": "内容", "style": "paragraph|heading1|heading2|heading3|bullet"} |
| replace_all | 全文替换文本 | {"old": "旧文本", "new": "新文本"} |

### XLSX 动作类型

| type | 说明 | 参数 |
|------|------|------|
| set_cell | 设置单元格值 | {"row": N, "col": N, "value": "新值"} |
| add_row | 添加数据行 | {"values": ["列1", "列2", ...]} 或 {"afterRow": N, "values": [...]} |

### INDEX 约定（重要！）

- 所有 index 从 0 开始（第一章 = chapterIndex: 0）
- 如果用户说"第三章"，你应该用 chapterIndex: 2
- 如果用户说"第二点"，你应该用 itemIndex: 1
- 如果用户说"第一个"，你应该用 index: 0

## 回复规则

1. 先用自然语言说明你做了什么修改，再给出 actions JSON
2. 如果没有修改操作，不要包含 ```json 块
3. 中文回复，简洁专业，不超过300字
4. 先确认理解用户意图
5. 当用户说要"修改""改成""加一个""删除"时，必须给出对应的 action"""


# ═══════════════════════════════════════════════════
# Agent 单例
# ═══════════════════════════════════════════════════

_agent: Optional[Agent] = None
_agent_hash: str = ""


def _get_agent(settings: Settings) -> Agent:
    global _agent, _agent_hash
    h = f"{settings.openai_api_key[:8]}:{settings.openai_model}"
    if _agent is None or _agent_hash != h:
        cred = DeepSeekCredential(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        model = DeepSeekChatModel(credential=cred, model=settings.openai_model)
        _agent = Agent(name="JeffreyAssistant", system_prompt=SYSTEM_PROMPT, model=model)
        _agent_hash = h
        logger.info("AgentScope Agent 已初始化: model=%s", settings.openai_model)
    return _agent


def _build_msg(body: ChatRequest) -> str:
    parts = []
    tab_names = {"ppt": "PPT生成", "docx": "文档写作", "xlsx": "表格工具"}
    parts.append(f"【当前模块】{tab_names.get(body.tab, body.tab or '主页')}")
    if body.title:
        parts.append(f"【标题】{body.title}")
    if body.context:
        parts.append(f"【文档内容】\n{body.context[:3500]}")
    parts.append(f"\n【用户请求】{body.message}")
    return "\n".join(parts)


def _parse_actions(reply: str) -> tuple[str, list[dict]]:
    """从回复中提取 JSON actions 块，分离纯文本和动作"""
    # 匹配 ```json ... ``` 块
    match = re.search(r'```json\s*\n?\s*(\{[\s\S]*?\})\s*\n?\s*```', reply)
    if not match:
        return reply.strip(), []

    try:
        payload = json.loads(match.group(1))
        actions = payload.get("actions", [])
    except json.JSONDecodeError:
        return reply.strip(), []

    # 从回复中移除 JSON 块
    clean = reply[:match.start()].strip() + "\n" + reply[match.end():].strip()
    return clean.strip(), actions


# ═══════════════════════════════════════════════════
# POST /api/chat_agent
# ═══════════════════════════════════════════════════

@router.post("/chat_agent", response_model=ChatResponse, summary="AI 文档助手对话")
async def chat_agent(body: ChatRequest, settings: Settings = Depends(get_settings)):
    if not settings.is_api_key_configured:
        raise HTTPException(status_code=503, detail={"error": "service_unavailable", "detail": "AI服务未配置"})

    start = time.monotonic()

    try:
        agent = _get_agent(settings)
        msg_text = _build_msg(body)
        result = await agent.reply(Msg(name="user", role="user", content=[TextBlock(type="text", text=msg_text)]))
        raw_reply = result.get_text_content() or "抱歉，我暂时无法回应。"

        # 解析 actions
        clean_reply, actions = _parse_actions(raw_reply)

        elapsed = time.monotonic() - start
        logger.info("Agent完成: tab=%s, 耗时%.2fs, actions=%d", body.tab, elapsed, len(actions))

        return ChatResponse(reply=clean_reply, tab=body.tab, actions=actions)

    except Exception as e:
        logger.exception("Agent失败")
        raise HTTPException(status_code=500, detail={"error": "agent_error", "detail": str(e)})
