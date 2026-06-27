from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class SlideStyle(str, Enum):
    """PPT风格枚举"""
    BUSINESS = "business"
    TECH = "tech"
    CREATIVE = "creative"

class SlideType(str, Enum):
    """幻灯片类型枚举"""
    COVER = "cover"
    CONTENT = "content"
    ENDING = "ending"

class GenerateRequest(BaseModel):
    """一键生成PPT请求（兼容旧版）"""
    prompt: str = Field(..., min_length=2, max_length=2000)
    pages: int = Field(default=10, ge=3, le=30)
    style: SlideStyle = Field(default=SlideStyle.BUSINESS)

class Slide(BaseModel):
    """幻灯片模型"""
    slide_number: int = Field(..., ge=1)
    type: SlideType
    title: str = Field(..., min_length=1)
    body: Optional[str] = Field(default=None)
    points: List[str] = Field(default_factory=list)
    background: str = Field(default="")

class GenerateResponse(BaseModel):
    """一键生成PPT响应"""
    slides: List[Slide]
    total_pages: int = Field(..., ge=1)
    style: str

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str = "1.0.0"
    project: str = "Jeffrey_AI_step_1st"

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: str


# ===================== 两步生成新增模型 =====================

class OutlineItem(BaseModel):
    """大纲条目"""
    title: str
    sub_items: List[str] = Field(default_factory=list)

class OutlineChapter(BaseModel):
    """大纲章节"""
    chapter_title: str
    items: List[OutlineItem] = Field(default_factory=list)

class GenerateOutlineRequest(BaseModel):
    """生成大纲请求"""
    prompt: str = Field(..., min_length=2, max_length=2000)
    pages: int = Field(default=10, ge=3, le=30)
    style: SlideStyle = Field(default=SlideStyle.BUSINESS)

class GenerateOutlineResponse(BaseModel):
    """生成大纲响应"""
    title: str
    chapters: List[OutlineChapter]
    total_pages: int
    style: str

class GenerateContentRequest(BaseModel):
    """生成内容请求"""
    title: str
    chapters: List[OutlineChapter]
    style: SlideStyle = Field(default=SlideStyle.BUSINESS)
    words_per_page: int = Field(default=150, ge=50, le=500)

class ContentSlide(BaseModel):
    """内容幻灯片"""
    slide_number: int
    type: SlideType
    chapter_title: str
    item_title: str
    title: str
    body: str
    points: List[str]
    background: str

class GenerateContentResponse(BaseModel):
    """生成内容响应"""
    slides: List[ContentSlide]
    total_pages: int
    style: str
    title: str


class ExportHTMLRequest(BaseModel):
    """导出HTML请求"""
    title: str
    slides: List[ContentSlide]
    style: str = "business"

# ===================== DOCX/XLSX 导出模型 =====================

class DocxBlock(BaseModel):
    type: str = Field(..., description='块类型: heading1|heading2|heading3|paragraph|bullet')
    text: str = Field(..., min_length=1)

class ExportDocxRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: List[DocxBlock] = Field(..., min_length=1)
    author: str = Field(default='Jeffrey_AI_step_1st')

class ExportXlsxRequest(BaseModel):
    title: str = Field(..., min_length=1)
    headers: List[str] = Field(..., min_length=1)
    rows: List[List[str]] = Field(default_factory=list)
