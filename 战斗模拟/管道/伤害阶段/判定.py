"""命中 / 闪避 / 格挡 / 暴击 判定阶段。"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.伤害阶段.辅助 import (
    取双方标签,
    取面板值,
    写入中间,
    攻方等级,
    守方等级,
    钳制,
    掷骰,
)
def 阶段_无敌(ctx: dict[str, Any]) -> dict[str, Any]:
    """守方含「无敌」则伤害归零（连必中也避开）。"""
    tags = 取双方标签(ctx.get("defender"))
    if "无敌" in tags:
        ctx["伤害"] = 0.0
        ctx["命中"] = False
        ctx["闪避"] = True
        ctx["终止"] = True
        写入中间(ctx, "无敌", 触发=True, 命中=False)
    else:
        写入中间(ctx, "无敌", 触发=False)
    return ctx


def 阶段_必中或必定闪避(ctx: dict[str, Any]) -> dict[str, Any]:
    """必中可穿透必定闪避 / 绝对回避。"""
    atags = 取双方标签(ctx.get("attacker"))
    dtags = 取双方标签(ctx.get("defender"))
    force_hit = bool(ctx.get("强制命中") or ("必中" in atags))
    must_dodge = ("必定闪避" in dtags) or ("绝对回避" in dtags)
    if must_dodge and not force_hit:
        ctx["伤害"] = 0.0
        ctx["命中"] = False
        ctx["闪避"] = True
        ctx["终止"] = True
        写入中间(ctx, "必中或必定闪避", 必中=force_hit, 必定闪避=True, 命中=False)
    else:
        ctx["强制命中"] = force_hit
        写入中间(ctx, "必中或必定闪避", 必中=force_hit, 必定闪避=must_dodge, 命中=True)
    return ctx


def _率或折算(
    ctx: dict[str, Any],
    *,
    曲线名: str,
    属性键: tuple[str, ...],
    面板率键: tuple[str, ...],
    侧: str,
    等级: float,
) -> float:
    """优先读已折算的面板率；否则用公式参数 k/c 折算属性量。"""
    side = ctx.get(侧) or {}
    for k in 面板率键:
        if k in side or (isinstance(side.get("面板"), dict) and k in side["面板"]):
            return 钳制(取面板值(side, k, default=0.0), 0.0, 1.0)
    fp = ctx.get("公式参数")
    raw = 取面板值(side, *属性键, default=0.0)
    if fp is not None and hasattr(fp, "有曲线") and fp.有曲线(曲线名):
        return 钳制(fp.折算(曲线名, raw, 等级), 0.0, 1.0)
    # 无曲线：若属性量已像率（≤1）直接用；否则无法折算→0
    if 0.0 < raw <= 1.0:
        return float(raw)
    return 0.0


def 阶段_属性闪避(ctx: dict[str, Any]) -> dict[str, Any]:
    """闪避效果 = clamp(闪避率 − 命中率, 0, 0.40)；必中跳过。"""
    if ctx.get("强制命中") or ctx.get("跳过闪避"):
        ctx["命中"] = True
        ctx["闪避"] = False
        写入中间(ctx, "属性闪避", 跳过=True, 闪避效果=0.0, 命中=True)
        return ctx

    atk_lv = 攻方等级(ctx)
    dfd_lv = 守方等级(ctx)
    # 闪避目前表内多为面板%（效果值=闪避%−命中%）；若有曲线则折算
    dodge_rate = _率或折算(
        ctx,
        曲线名="闪避率",
        属性键=("闪避", "闪避值"),
        面板率键=("闪避率", "闪避%", "闪避率%"),
        侧="defender",
        等级=dfd_lv,
    )
    hit_rate = _率或折算(
        ctx,
        曲线名="命中率",
        属性键=("命中", "命中值"),
        面板率键=("命中率", "命中%", "命中率%"),
        侧="attacker",
        等级=atk_lv,
    )
    # 允许直接给「闪避效果」
    if "闪避效果" in (ctx.get("defender") or {}):
        dodge_eff = 钳制(取面板值(ctx.get("defender"), "闪避效果"), 0.0, 0.40)
    else:
        dodge_eff = 钳制(dodge_rate - hit_rate, 0.0, 0.40)

    ctx["闪避效果"] = dodge_eff
    if ctx.get("期望模式"):
        p_hit = 1.0 - dodge_eff
        ctx["命中"] = True  # EV 路径继续乘 p_hit
        ctx["闪避"] = False
        ctx["命中概率"] = p_hit
        ctx["伤害"] = float(ctx["伤害"]) * p_hit
        写入中间(ctx, "属性闪避", 闪避效果=dodge_eff, 命中概率=p_hit, 期望=True)
        return ctx

    roll = 掷骰(ctx)
    dodged = roll < dodge_eff
    if dodged:
        ctx["伤害"] = 0.0
        ctx["命中"] = False
        ctx["闪避"] = True
        ctx["终止"] = True
        写入中间(ctx, "属性闪避", 闪避效果=dodge_eff, 掷骰=roll, 命中=False)
    else:
        ctx["命中"] = True
        ctx["闪避"] = False
        写入中间(ctx, "属性闪避", 闪避效果=dodge_eff, 掷骰=roll, 命中=True)
    return ctx


def 阶段_格挡(ctx: dict[str, Any]) -> dict[str, Any]:
    """格挡效果 = clamp(格挡率 − 精准率, 0, 1)；格挡免伤底 +0.40。与暴击互斥。"""
    if ctx.get("禁止格挡"):
        ctx["格挡"] = False
        ctx["格挡免伤效果"] = 0.0
        写入中间(ctx, "格挡", 跳过=True)
        return ctx

    atk_lv = 攻方等级(ctx)
    dfd_lv = 守方等级(ctx)
    block_rate = _率或折算(
        ctx,
        曲线名="格挡率",
        属性键=("格挡",),
        面板率键=("格挡率", "格挡%"),
        侧="defender",
        等级=dfd_lv,
    )
    prec_rate = _率或折算(
        ctx,
        曲线名="精准率",
        属性键=("精准",),
        面板率键=("精准率", "精准%"),
        侧="attacker",
        等级=atk_lv,
    )
    block_eff = 钳制(block_rate - prec_rate, 0.0, 1.0)
    if "格挡效果" in (ctx.get("defender") or {}) or "格挡效果" in (ctx.get("attacker") or {}):
        block_eff = 钳制(
            取面板值(ctx.get("defender"), "格挡效果", default=取面板值(ctx.get("attacker"), "格挡效果")),
            0.0,
            1.0,
        )
    ctx["格挡效果"] = block_eff

    # 格挡免伤效果 = clamp(格挡免伤% − 格挡穿透% + 0.40, 0, 0.75)
    block_mit_raw = (
        取面板值(ctx.get("defender"), "格挡免伤%", "格挡免伤", default=0.0)
        - 取面板值(ctx.get("attacker"), "格挡穿透%", "格挡穿透", default=0.0)
        + 0.40
    )
    block_mit = 钳制(block_mit_raw, 0.0, 0.75)
    ctx["格挡免伤效果"] = block_mit

    if ctx.get("期望模式"):
        ctx["格挡"] = False
        ctx["格挡概率"] = block_eff
        # EV：在暴击阶段合并期望乘子；此处只记录
        写入中间(ctx, "格挡", 格挡效果=block_eff, 格挡免伤效果=block_mit, 期望=True)
        return ctx

    roll = 掷骰(ctx)
    blocked = roll < block_eff
    ctx["格挡"] = blocked
    if blocked:
        ctx["伤害"] = float(ctx["伤害"]) * (1.0 - block_mit)
        写入中间(ctx, "格挡", 触发=True, 格挡效果=block_eff, 格挡免伤效果=block_mit, 掷骰=roll)
    else:
        写入中间(ctx, "格挡", 触发=False, 格挡效果=block_eff, 掷骰=roll)
    return ctx


def 阶段_暴击(ctx: dict[str, Any]) -> dict[str, Any]:
    """暴击效果 = clamp(暴击率 − 抗暴率, 0, 1)；与格挡互斥。"""
    if ctx.get("禁止暴击") or ctx.get("格挡"):
        ctx["暴击"] = False
        写入中间(ctx, "暴击", 跳过=True, 因格挡=bool(ctx.get("格挡")))
        return ctx

    atk_lv = 攻方等级(ctx)
    dfd_lv = 守方等级(ctx)
    crit_rate = _率或折算(
        ctx,
        曲线名="暴击率",
        属性键=("暴击",),
        面板率键=("暴击率", "暴击%"),
        侧="attacker",
        等级=atk_lv,
    )
    anti_rate = _率或折算(
        ctx,
        曲线名="抗暴率",
        属性键=("抗暴",),
        面板率键=("抗暴率", "抗暴%"),
        侧="defender",
        等级=dfd_lv,
    )
    crit_eff = 钳制(crit_rate - anti_rate, 0.0, 1.0)
    if "暴击效果" in (ctx.get("attacker") or {}):
        crit_eff = 钳制(取面板值(ctx.get("attacker"), "暴击效果"), 0.0, 1.0)
    ctx["暴击效果"] = crit_eff

    if ctx.get("期望模式"):
        ctx["暴击"] = False
        ctx["暴击概率"] = crit_eff
        写入中间(ctx, "暴击", 暴击效果=crit_eff, 期望=True)
        return ctx

    roll = 掷骰(ctx)
    crit = roll < crit_eff
    ctx["暴击"] = crit
    写入中间(ctx, "暴击", 触发=crit, 暴击效果=crit_eff, 掷骰=roll)
    return ctx
