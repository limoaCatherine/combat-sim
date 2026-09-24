"""技能价值：表内系数 × 面板；1-ply 择技。禁止技能 id 哈希伪分。"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def 感知快照(
    *,
    now_ms: float = 0.0,
    self_hp: float = 0.0,
    self_hp_max: float = 1.0,
    target_hp: float = 0.0,
    target_hp_max: float = 1.0,
    gcd_ready_at: float = 0.0,
    busy_until: float = 0.0,
    resources: dict[str, float] | None = None,
    buffs: list[str] | None = None,
    distance: float = 1.0,
) -> dict[str, Any]:
    sm = float(self_hp_max) if float(self_hp_max) else 1.0
    tm = float(target_hp_max) if float(target_hp_max) else 1.0
    return {
        "now_ms": float(now_ms),
        "自身HP": float(self_hp),
        "自身HP上限": sm,
        "自身HP%": float(self_hp) / sm,
        "目标HP": float(target_hp),
        "目标HP上限": tm,
        "目标HP%": float(target_hp) / tm,
        "GCD剩余ms": max(0.0, float(gcd_ready_at) - float(now_ms)),
        "忙碌剩余ms": max(0.0, float(busy_until) - float(now_ms)),
        "resources": dict(resources or {}),
        "buffs": list(buffs or []),
        "distance": float(distance),
    }


def _行数字(技能: Any, *keys: str) -> float | None:
    raw = getattr(技能, "原始行", None)
    if not isinstance(raw, dict):
        return None
    for k in keys:
        v = raw.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def 估算基础伤害(技能: Any, panel: Mapping[str, Any] | None = None) -> float:
    pan = dict(panel or {})
    seg = str(getattr(技能, "伤害段", "") or "")
    if seg.strip():
        from 战斗模拟.领域.面板表达式 import 切段, 求值

        total = 0.0
        for part in 切段(seg):
            total += float(求值(part, pan))
        return total
    expected = getattr(技能, "期望伤害", None)
    if expected is not None and str(expected).strip() not in ("", "—", "-", "无"):
        return float(expected)
    coeff = getattr(技能, "期望伤害系数", None)
    if coeff is None:
        coeff = _行数字(技能, "期望伤害系数", "伤害系数", "段期望系数")
    if coeff is None:
        try:
            c2 = getattr(技能, "段期望系数", None)
            coeff = float(c2) if c2 not in (None, "") else None
        except (TypeError, ValueError):
            coeff = None
    raw = getattr(技能, "原始行", None)
    axis = str(getattr(技能, "伤害轴", "") or "").strip()
    if not axis and isinstance(raw, dict):
        axis = str(raw.get("伤害轴") or "").strip()
    if coeff is None:
        raise ValueError("无伤害段且无期望伤害系数")
    if not axis:
        raise ValueError("无伤害段且无伤害轴")
    if axis not in pan or not isinstance(pan.get(axis), (int, float)):
        raise ValueError(f"面板缺伤害轴 {axis}")
    return float(coeff) * float(pan[axis])


def 估算基础治疗(技能: Any, panel: Mapping[str, Any] | None = None) -> float:
    pan = dict(panel or {})
    expr = str(getattr(技能, "治疗解析式", "") or "")
    if expr.strip():
        from 战斗模拟.领域.面板表达式 import 求值

        return float(求值(expr, pan))
    coeff = getattr(技能, "期望HPS", None) or _行数字(技能, "期望HPS", "治疗系数")
    heal_stat = float(pan.get("治疗强度") or pan.get("魔法攻击") or 0.0)
    if coeff is not None and heal_stat:
        return float(coeff) * heal_stat
    return 0.0


def 选技_1ply(
    候选: Sequence[Any],
    快照: Mapping[str, Any],
    panel: Mapping[str, Any] | None = None,
):
    from 战斗模拟.ai.状态决策 import 选择动作

    return 选择动作(快照, 候选, panel=panel)


def 技能公式分(skill_id: str, ctx: dict[str, Any] | None = None) -> float:
    """用上下文里已加载的技能行系数×面板，不用 id 哈希。"""
    ctx = ctx or {}
    row = ctx.get("技能") or ctx.get("技能行")
    panel = ctx.get("panel") or ctx.get("面板") or {}
    if row is None:
        catalog = ctx.get("技能目录")
        if catalog is not None and hasattr(catalog, "取"):
            try:
                row = catalog.取(skill_id)
            except Exception:
                row = None
    if row is None:
        raise ValueError(f"技能公式分无表行: {skill_id}")
    return 估算基础伤害(row, panel)


def 选技_价值(候选: list[str], ctx: dict[str, Any] | None = None) -> str | None:
    if not 候选:
        return None
    return max(候选, key=lambda s: 技能公式分(s, ctx))


skill_formula_score = 技能公式分
choose_by_value = 选技_价值
sense_snapshot = 感知快照
estimate_base_damage = 估算基础伤害
estimate_base_heal = 估算基础治疗
