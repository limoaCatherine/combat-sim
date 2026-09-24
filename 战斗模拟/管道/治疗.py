"""治疗管线：基础治疗 → 施法治疗效果 × 受治疗效果 → 可选治疗暴击 → 收束 → 回血/[PVE仇恨]。

对齐框架「治疗*」与 UGit HealCrit*：暴击仅施疗者暴击率（无抗暴），暴伤仅暴击伤害%（无暴伤抗）。
算量后：调用结算(回血,治疗值) → [PVE] 设治疗仇恨(治疗值*0.05*仇恨系数) → 治疗结束。
吸血回血不经本管线（见伤害* → 回血*）。

效果目标绑定（与战斗流程 DSL 一致）
--------------------------------
- 施法治疗效果 / HealEffect* → **攻方**（healer/caster）面板
- 受治疗效果 / RecvHeal* → **守方**（heal recipient / target）面板
- 治疗暴击效果* / 治疗暴击伤害效果* → **攻方** only（无 antirate）
"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.注册表 import 注册


def _panel(side: dict[str, Any] | None, *keys: str, default: float = 0.0) -> float:
    panel = side or {}
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


def _heal_cast_mult(healer: dict[str, Any]) -> float:
    """施法治疗效果：从 **攻方/healer** 面板取；优先效果乘数，否则 1+治疗加成%。"""
    for k in ("施法治疗效果", "HealEffectPVE", "HealEffectPVP", "HealEffect"):
        v = _panel(healer, k, default=0.0)
        if v > 1.0 or (k in healer and v > 0):
            if v > 0:
                return v if v >= 1.0 else 1.0 + v
    pct = _panel(healer, "治疗效果%", "治疗加成%", "HealPct", default=0.0)
    return 1.0 + pct


def _heal_recv_mult(target: dict[str, Any]) -> float:
    """受治疗效果：从 **守方/target** 面板取；优先效果乘数，否则 1+受治疗加成%。"""
    for k in ("受治疗效果", "RecvHealEffectPVE", "RecvHealEffectPVP", "RecvHealEffect"):
        v = _panel(target, k, default=0.0)
        if v > 1.0 or (k in target and v > 0):
            if v > 0:
                return v if v >= 1.0 else 1.0 + v
    pct = _panel(target, "受治疗加成%", "HealTakenPct", default=0.0)
    return 1.0 + pct


def 解析治疗PVE(
    *,
    基础治疗: float,
    healer: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    可暴击: bool = False,
    期望模式: bool = False,
    rng: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    healer = healer or {}  # 攻方 / caster panel
    target = target or {}  # 守方 / heal recipient panel
    base = float(基础治疗)
    cast_mult = _heal_cast_mult(healer)   # 效果(施法治疗效果*,攻方)
    recv_mult = _heal_recv_mult(target)   # 效果(受治疗效果*,守方)
    amount = base * cast_mult * recv_mult

    crit = False
    p_crit = 0.0
    crit_mult = 1.0
    if 可暴击:
        # HealCrit：仅暴击率钳制，无抗暴；优先治疗暴击效果键
        p_crit = _panel(
            healer,
            "治疗暴击效果",
            "HealCritEffectPVE",
            "HealCritEffect",
            default=-1.0,
        )
        if p_crit < 0:
            p_crit = max(0.0, min(1.0, _panel(healer, "暴击率", "暴击%", default=0.0)))
        else:
            p_crit = max(0.0, min(1.0, p_crit))
        crit_mult = _panel(
            healer,
            "治疗暴击伤害效果",
            "HealCritDmgEffectPVE",
            "HealCritDmgEffect",
            default=0.0,
        )
        if crit_mult <= 0:
            # 钳制(2+暴击伤害%,1.5,4)
            raw = 2.0 + _panel(healer, "暴击伤害%", "暴击伤害", "CritDMGPct", default=0.0)
            crit_mult = max(1.5, min(4.0, raw))
        # 兼容旧测试键 暴击效果/暴击伤害效果（若未给 HealCrit*）
        if _panel(healer, "治疗暴击效果", "HealCritEffectPVE", "HealCritEffect", default=-1.0) < 0:
            legacy = _panel(healer, "暴击效果", default=-1.0)
            if legacy >= 0:
                p_crit = max(0.0, min(1.0, legacy))
            legacy_m = _panel(healer, "暴击伤害效果", default=0.0)
            if legacy_m > 0:
                crit_mult = legacy_m
        if 期望模式:
            amount *= (1.0 - p_crit) + p_crit * crit_mult
        else:
            roll = float(rng.random()) if rng is not None else 1.0
            crit = roll < p_crit
            if crit:
                amount *= crit_mult

    hp = _panel(target, "生命", "hp", "当前生命", default=0.0)
    hp_max = _panel(target, "生命上限", "hp_max", "生命值", default=0.0)
    if hp_max > 0:
        room = max(0.0, hp_max - hp)
        applied = min(amount, room)
        overheal = max(0.0, amount - applied)
    else:
        applied = amount
        overheal = 0.0

    return {
        "治疗": float(applied),
        "原始治疗": float(amount),
        "过量治疗": float(overheal),
        "基础治疗": base,
        "施法治疗效果乘数": cast_mult,
        "受治疗效果乘数": recv_mult,
        "治疗效果乘数": cast_mult * recv_mult,
        "暴击": crit,
        "治疗暴击效果": p_crit,
        "治疗暴击伤害效果": crit_mult,
        "暴击效果": p_crit,
        "暴击伤害效果": crit_mult,
        "healer": healer,
        "target": target,
        "阶段日志": [
            "应用施法治疗",
            "应用受治疗",
            "判定治疗暴击" if 可暴击 else "跳过暴击",
            "应用治疗暴击" if 可暴击 else "跳过暴击应用",
            "治疗收束",
        ],
        "模式": "PVE",
        **extra,
    }


def 解析治疗PVP(**kwargs: Any) -> dict[str, Any]:
    out = 解析治疗PVE(**kwargs)
    out["模式"] = "PVP"
    return out


注册("heal_pve", 解析治疗PVE)
注册("治疗PVE", 解析治疗PVE)
注册("heal_pvp", 解析治疗PVP)
注册("治疗PVP", 解析治疗PVP)

resolve_heal_pve = 解析治疗PVE
