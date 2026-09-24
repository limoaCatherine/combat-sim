"""简单优先级列表（APL）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class APL条目:
    技能: str
    条件: str = "True"  # 表达式占位
    优先级: int = 0


def 选技_优先级(条目列表: list[APL条目], 可用: set[str]) -> str | None:
    ordered = sorted(条目列表, key=lambda x: -x.优先级)
    for e in ordered:
        if e.技能 in 可用:
            return e.技能
    return None


choose_by_apl = 选技_优先级
