from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

class SlideStyle(str, Enum):
    BUSINESS =  business
    TECH = tech
    CREATIVE = creative

class SlideType(str, Enum):
    COVER = cover
    CONTENT = content
    ENDING = ending

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=2000, description=PPT主题描述)
    pages: int = Field(default=10, ge=3, le=30, description=期望页数)
    style: SlideStyle = Field(default=SlideStyle.BUSINESS, description=风格)

    @field_validator(prompt)
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError(主题描述至少2个字符)
        return cleaned

class Slide(BaseModel):
    slide_number: int = Field(..., ge=1)
    type: SlideType
    title: str = Field(..., min_length=1)
    body: Optional[str] = Field(default=None)
    points: List[str] = Field(default_factory=list)
    background: str = Field(default=)

class GenerateResponse(BaseModel):
 slides: List[Slide]
 total_pages: int = Field(..., ge=1)
 style: str

class HealthResponse(BaseModel):
 status: str = ok
 version: str = 1.0.0

class ErrorResponse(BaseModel):
 error: str
 detail: str
