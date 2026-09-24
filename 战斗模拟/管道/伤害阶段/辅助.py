"""伤害阶段共用辅助。"""
from __future__ import annotations

from typing import Any


def 取面板值(side: dict[str, Any] | None, *keys: str, default: float = 0.0) -> float:
    panel = side or {}
    # 支持扁平实体 dict 或 嵌套「面板」
    nested = panel.get("面板") if isinstance(panel.get("面板"), dict) else None
    for k in keys:
        if k in panel and panel[k] is not None:
            try:
                return float(panel[k])
            except (TypeError, ValueError):
                pass
        if nested and k in nested and nested[k] is not None:
            try:
                return float(nested[k])
            except (TypeError, ValueError):
                pass
    return float(default)


def 取双方标签(side: dict[str, Any] | None) -> set[str]:
    if not side:
        return set()
    raw = side.get("标签") or side.get("tags") or ()
    if isinstance(raw, set):
        return set(raw)
    if isinstance(raw, (list, tuple)):
        return {str(x) for x in raw}
    if isinstance(raw, str) and raw.strip():
        return {p.strip() for p in raw.replace("|", ",").split(",") if p.strip()}
    return set()


def 钳制(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def 写入中间(ctx: dict[str, Any], 阶段名: str, **kv: Any) -> None:
    mid = ctx.setdefault("中间结果", {})
    mid[阶段名] = {**kv, "伤害": float(ctx.get("伤害", 0.0))}
    ctx.setdefault("阶段日志", []).append(阶段名)


def 攻方等级(ctx: dict[str, Any]) -> float:
    atk = ctx.get("attacker") or {}
    return float(atk.get("等级") or atk.get("level") or ctx.get("等级") or 1)


def 守方等级(ctx: dict[str, Any]) -> float:
    dfd = ctx.get("defender") or {}
    return float(dfd.get("等级") or dfd.get("level") or ctx.get("等级") or 攻方等级(ctx))


def 掷骰(ctx: dict[str, Any]) -> float:
    """返回 [0,1)。期望模式返回 1.0（由调用方用概率期望，不掷）。"""
    if ctx.get("期望模式"):
        return 1.0
    rng = ctx.get("rng")
    if rng is not None:
        return float(rng.random())
    # 无 RNG：确定性（视为不触发概率事件，除非强制）
    return 1.0
