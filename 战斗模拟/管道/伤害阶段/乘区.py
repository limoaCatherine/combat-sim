"""免伤 / 克制 / 伤害乘区 / 爆伤 / 吸血反伤 / 受伤修正。"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.伤害阶段.辅助 import (
    取面板值,
    写入中间,
    攻方等级,
    钳制,
)
from 战斗模拟.load.公式参数 import 折算对抗率


def _率或折算(
    ctx: dict[str, Any],
    *,
    曲线名: str,
    属性键: tuple[str, ...],
    面板率键: tuple[str, ...],
    侧: str,
    等级: float,
) -> float:
    side = ctx.get(侧) or {}
    for k in 面板率键:
        if k in side or (isinstance(side.get("面板"), dict) and k in side["面板"]):
            return 钳制(取面板值(side, k, default=0.0), 0.0, 1.0)
    fp = ctx.get("公式参数")
    raw = 取面板值(side, *属性键, default=0.0)
    if fp is not None and hasattr(fp, "有曲线") and fp.有曲线(曲线名):
        return 钳制(fp.折算(曲线名, raw, 等级), 0.0, 1.0)
    if 0.0 < raw <= 1.0:
        return float(raw)
    # 无曲线时用默认 k/c 兜底（仅当属性量>1，便于无表单测）
    if raw > 1.0:
        return 钳制(折算对抗率(raw, 30.0, 10.0, 等级), 0.0, 1.0)
    return 0.0


def 阶段_免伤(ctx: dict[str, Any]) -> dict[str, Any]:
    """物/魔免伤效果 = clamp(免伤率 − 穿透率, 0, 0.75)；真实伤害免伤=0。"""
    kind = str(ctx.get("伤害类型") or ctx.get("kind") or "物理")
    is_true = "真实" in kind
    is_phys = (not is_true) and ("物理" in kind or kind == "")
    if is_true:
        mit = 0.0
        ctx["免伤效果"] = 0.0
        写入中间(ctx, "免伤", 真实=True, 免伤效果=0.0)
        return ctx

    atk_lv = 攻方等级(ctx)
    if is_phys:
        mit_rate = _率或折算(
            ctx,
            曲线名="物理免伤率",
            属性键=("物理防御", "物防", "防御"),
            面板率键=("物理免伤率", "物理免伤率%", "免伤率%"),
            侧="defender",
            等级=atk_lv,  # 分母用攻方等级
        )
        pen_rate = _率或折算(
            ctx,
            曲线名="物理穿透率",
            属性键=("物理穿透", "物防穿透"),
            面板率键=("物理穿透率", "物理穿透率%"),
            侧="attacker",
            等级=atk_lv,
        )
    else:
        mit_rate = _率或折算(
            ctx,
            曲线名="魔法免伤率",
            属性键=("魔法防御", "魔防"),
            面板率键=("魔法免伤率", "魔法免伤率%"),
            侧="defender",
            等级=atk_lv,
        )
        pen_rate = _率或折算(
            ctx,
            曲线名="魔法穿透率",
            属性键=("魔法穿透", "魔防穿透"),
            面板率键=("魔法穿透率", "魔法穿透率%"),
            侧="attacker",
            等级=atk_lv,
        )

    mit = 钳制(mit_rate - pen_rate, 0.0, 0.75)
    # 允许直接覆盖
    key = "物理免伤效果" if is_phys else "魔法免伤效果"
    if key in (ctx.get("defender") or {}):
        mit = 钳制(取面板值(ctx.get("defender"), key), 0.0, 0.75)
    ctx["免伤效果"] = mit
    ctx["伤害"] = float(ctx["伤害"]) * (1.0 - mit)
    写入中间(
        ctx,
        "免伤",
        通道="物理" if is_phys else "魔法",
        免伤率=mit_rate,
        穿透率=pen_rate,
        免伤效果=mit,
    )
    return ctx


def 阶段_克制(ctx: dict[str, Any]) -> dict[str, Any]:
    """简化克制：维间 More。默认 1.0；可读「克制倍率」或元素/种族/体型加成。"""
    atk = ctx.get("attacker") or {}
    dfd = ctx.get("defender") or {}
    # 直接倍率优先
    mod = 取面板值(atk, "克制倍率", default=1.0)
    if mod == 1.0 and "克制倍率" not in atk:
        # 简化：元素/种族/体型 Increase 相加后再 More
        el = 1.0 + 取面板值(atk, "元素增伤%", "对应元素增伤", default=0.0) - 取面板值(
            dfd, "元素抗性%", "对应元素抗性", default=0.0
        )
        race = 1.0 + 取面板值(atk, "种族增伤%", "对应种族增伤", default=0.0) - 取面板值(
            dfd, "种族抗性%", "对应种族抗性", default=0.0
        )
        size = 1.0 + 取面板值(atk, "体型增伤%", "对应体型增伤", default=0.0) - 取面板值(
            dfd, "体型抗性%", "对应体型抗性", default=0.0
        )
        matrix = 取面板值(atk, "元素克制矩阵倍率", default=1.0)
        mod = max(0.0, matrix * el * race * size)
    ctx["克制倍率"] = mod
    ctx["伤害"] = float(ctx["伤害"]) * mod
    写入中间(ctx, "克制", 克制倍率=mod)
    return ctx


def 阶段_伤害乘区(ctx: dict[str, Any]) -> dict[str, Any]:
    """伤害效果 Increase：1 + 增伤 − 抗性（简化单池）。"""
    kind = str(ctx.get("伤害类型") or "物理")
    if "真实" in kind:
        ctx["伤害乘区"] = 1.0
        写入中间(ctx, "伤害乘区", 真实=True, 倍率=1.0)
        return ctx
    atk = ctx.get("attacker") or {}
    dfd = ctx.get("defender") or {}
    amp = 取面板值(atk, "最终增伤%", "全伤害提高", "伤害提高%", default=0.0)
    red = 取面板值(dfd, "最终免伤%", "全伤害减免", "伤害减免%", default=0.0)
    # 通道
    if "魔法" in kind:
        amp += 取面板值(atk, "魔法增伤%", default=0.0)
        red += 取面板值(dfd, "魔法抗性%", default=0.0)
    else:
        amp += 取面板值(atk, "物理增伤%", default=0.0)
        red += 取面板值(dfd, "物理抗性%", default=0.0)
    mod = 1.0 + amp - red
    if "伤害乘区" in atk:
        mod = 取面板值(atk, "伤害乘区", default=mod)
    ctx["伤害乘区"] = mod
    ctx["伤害"] = float(ctx["伤害"]) * max(0.0, mod)
    写入中间(ctx, "伤害乘区", 倍率=mod, 增伤=amp, 抗性=red)
    return ctx


def 阶段_暴击伤害(ctx: dict[str, Any]) -> dict[str, Any]:
    """暴击伤害效果 = 1.50 + 暴击伤害% − 爆伤减免%（表内亦见 2.00 底；此处用 1.50 对齐架构）。"""
    atk = ctx.get("attacker") or {}
    dfd = ctx.get("defender") or {}
    base = float(ctx.get("暴击伤害底") or 1.50)
    crit_dmg = base + 取面板值(atk, "暴击伤害%", "暴击伤害", default=0.0) - 取面板值(
        dfd, "爆伤减免%", "爆伤减免", "暴伤抗性%", default=0.0
    )
    if "暴击伤害效果" in atk:
        crit_dmg = 取面板值(atk, "暴击伤害效果", default=crit_dmg)
    ctx["暴击伤害效果"] = crit_dmg

    if ctx.get("期望模式"):
        pb = float(ctx.get("格挡概率") or 0.0)
        pc = float(ctx.get("暴击概率") or 0.0)
        block_mit = float(ctx.get("格挡免伤效果") or 0.0)
        # e_mult = pb*(1-block_mit) + (1-pb)*((1-pc)+pc*crit_dmg)
        e_mult = pb * (1.0 - block_mit) + (1.0 - pb) * ((1.0 - pc) + pc * crit_dmg)
        ctx["伤害"] = float(ctx["伤害"]) * e_mult
        写入中间(ctx, "暴击伤害", 期望乘子=e_mult, 暴击伤害效果=crit_dmg)
        return ctx

    if ctx.get("暴击"):
        ctx["伤害"] = float(ctx["伤害"]) * crit_dmg
        写入中间(ctx, "暴击伤害", 触发=True, 暴击伤害效果=crit_dmg)
    else:
        写入中间(ctx, "暴击伤害", 触发=False, 暴击伤害效果=crit_dmg)
    return ctx


def 阶段_吸血反伤(ctx: dict[str, Any]) -> dict[str, Any]:
    """吸血 / 反伤：各一条效果，不封顶。"""
    kind = str(ctx.get("伤害类型") or "物理")
    atk = ctx.get("attacker") or {}
    dfd = ctx.get("defender") or {}
    dmg = float(ctx.get("伤害") or 0.0)
    if "魔法" in kind:
        leech = 取面板值(atk, "魔法吸血", "吸血效果", "全吸血", default=0.0)
        reflect = 取面板值(dfd, "魔法反伤", "反伤效果", "全反伤", default=0.0)
    else:
        leech = 取面板值(atk, "物理吸血", "吸血效果", "全吸血", default=0.0)
        reflect = 取面板值(dfd, "物理反伤", "反伤效果", "全反伤", default=0.0)
    leech += 取面板值(atk, "全能吸血%", default=0.0)
    reflect += 取面板值(dfd, "全能反伤%", default=0.0)
    ctx["吸血"] = max(0.0, dmg * leech)
    ctx["反伤"] = max(0.0, dmg * reflect)
    写入中间(ctx, "吸血反伤", 吸血比例=leech, 反伤比例=reflect, 吸血=ctx["吸血"], 反伤=ctx["反伤"])
    return ctx


def 阶段_受伤修正(ctx: dict[str, Any]) -> dict[str, Any]:
    """效果「受伤±」；无则 1。"""
    dfd = ctx.get("defender") or {}
    factor = 取面板值(dfd, "受伤修正", "受伤%", default=1.0)
    # 若给的是加成量（如 0.1 表示 +10%），键名含 % 时按 1+x
    if "受伤%" in dfd and "受伤修正" not in dfd:
        factor = 1.0 + float(factor)
    ctx["受伤修正"] = factor
    ctx["伤害"] = max(0.0, float(ctx["伤害"]) * factor)
    写入中间(ctx, "受伤修正", 倍率=factor)
    return ctx
