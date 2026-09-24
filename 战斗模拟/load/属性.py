"""属性相关类型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class 属性值(BaseModel):
    名称: str
    数值: float | None = None
    层: str | None = None


class 属性面板(BaseModel):
    """扁平属性面板（B3 当前口径：终值常量）。"""
    构筑: str
    属性: dict[str, float | None] = Field(default_factory=dict)
    离散: dict[str, str] = Field(default_factory=dict)
