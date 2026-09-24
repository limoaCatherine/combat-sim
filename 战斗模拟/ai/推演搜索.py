"""预算化浅层搜索 stub（默认仍 1-ply）。"""
from __future__ import annotations

from typing import Any

from 战斗模拟.ai.技能价值 import 选技_价值


def 束搜索选技(
    候选: list[str],
    *,
    束宽: int = 4,
    深度: int = 1,
    ctx: dict[str, Any] | None = None,
) -> str | None:
    """深度≥2 时预留 2-ply；当前退回 1-ply 价值。"""
    del 束宽
    if 深度 <= 1:
        return 选技_价值(候选, ctx)
    # TODO: B × (1 fork + 公式分第二手)
    return 选技_价值(候选, ctx)


budgeted_rollout = 束搜索选技
