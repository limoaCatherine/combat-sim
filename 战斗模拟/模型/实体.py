"""战斗实体骨架。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class 实体(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    名称: str = ""
    阵营: str = "友方"  # 友方 / 敌方
    等级: int
    生命: float
    生命上限: float
    面板: dict[str, float] = Field(default_factory=dict)
    标签: set[str] = Field(default_factory=set)
    状态: set[str] = Field(default_factory=set)
    护盾层: list[dict[str, Any]] = Field(default_factory=list)
    光环列表: list[Any] = Field(default_factory=list)
    存活: bool = True
    # 可选空间坐标（光环半径 / 次要目标「最近」）；缺省则路由忽略半径
    位置x: float | None = None
    位置y: float | None = None
    位置: Any = None  # (x,y) / {"x","y"} 兼容字段

    def 拥有标签(self, *tokens: str) -> bool:
        return any(t in self.标签 for t in tokens)


Entity = 实体
