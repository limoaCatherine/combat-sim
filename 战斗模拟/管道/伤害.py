"""伤害管线：分阶段可测试结算。

权威顺序（对齐架构 + consolidate）：
无敌 → 必中/必定闪避 → 属性闪避 → 免伤 → 克制 → 格挡 → 暴击
→ 伤害乘区 → 暴击伤害 → 受伤修正 → 写出最终伤害
→ 【内联】零伤/闪避短路或物/魔通道 → 计算吸血量/反伤量
→ 守方扣血 → 吸血回血 → 反伤扣血
→ [PVE] 写出伤害仇恨 / 因死亡跳过仇恨 → 伤害结束

可调用结算子管线：仅 扣血* / 回血*。吸血反伤/仇恨为表内步骤（helpers 可选）。
"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.注册表 import 注册
from 战斗模拟.管道.伤害阶段 import (
    阶段_无敌,
    阶段_必中或必定闪避,
    阶段_属性闪避,
    阶段_免伤,
    阶段_克制,
    阶段_格挡,
    阶段_暴击,
    阶段_伤害乘区,
    阶段_暴击伤害,
    阶段_受伤修正,
    阶段_吸血反伤,
)

# 对外稳定顺序（测试断言用）
DAMAGE_PVE_STAGES: tuple[str, ...] = (
    "无敌",
    "必中或必定闪避",
    "属性闪避",
    "免伤",
    "克制",
    "格挡",
    "暴击",
    "伤害乘区",
    "暴击伤害",
    "受伤修正",
    "吸血反伤",
)

_STAGE_FUNCS = {
    "无敌": 阶段_无敌,
    "必中或必定闪避": 阶段_必中或必定闪避,
    "属性闪避": 阶段_属性闪避,
    "免伤": 阶段_免伤,
    "克制": 阶段_克制,
    "格挡": 阶段_格挡,
    "暴击": 阶段_暴击,
    "伤害乘区": 阶段_伤害乘区,
    "暴击伤害": 阶段_暴击伤害,
    "受伤修正": 阶段_受伤修正,
    "吸血反伤": 阶段_吸血反伤,
}


def 解析伤害PVE(
    *,
    基础伤害: float,
    attacker: dict[str, Any] | None = None,
    defender: dict[str, Any] | None = None,
    伤害类型: str = "物理",
    公式参数: Any = None,
    rng: Any = None,
    期望模式: bool = False,
    强制命中: bool = False,
    跳过闪避: bool = False,
    禁止格挡: bool = False,
    禁止暴击: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """按有序阶段结算，返回含「中间结果」的 dict。"""
    ctx: dict[str, Any] = {
        "伤害": float(基础伤害),
        "基础伤害": float(基础伤害),
        "最终伤害": 0.0,
        "伤害类型": 伤害类型,
        "attacker": attacker or {},
        "defender": defender or {},
        "公式参数": 公式参数,
        "rng": rng,
        "期望模式": 期望模式,
        "强制命中": 强制命中,
        "跳过闪避": 跳过闪避,
        "禁止格挡": 禁止格挡,
        "禁止暴击": 禁止暴击,
        "命中": True,
        "闪避": False,
        "格挡": False,
        "暴击": False,
        "吸血": 0.0,
        "反伤": 0.0,
        "阶段日志": [],
        "已执行阶段": [],
        "中间结果": {},
        "终止": False,
        "模式": "PVE",
        **extra,
    }
    for name in DAMAGE_PVE_STAGES:
        if ctx.get("终止"):
            break
        ctx = _STAGE_FUNCS[name](ctx)
        ctx.setdefault("已执行阶段", []).append(name)
    ctx["最终伤害"] = max(0.0, float(ctx.get("伤害") or 0.0))
    ctx["伤害"] = ctx["最终伤害"]
    return ctx


def 解析伤害PVP(**kwargs: Any) -> dict[str, Any]:
    out = 解析伤害PVE(**kwargs)
    out["模式"] = "PVP"
    return out


注册("damage_pve", 解析伤害PVE)
注册("伤害PVE", 解析伤害PVE)
注册("damage_pvp", 解析伤害PVP)
注册("伤害PVP", 解析伤害PVP)

resolve_damage_pve = 解析伤害PVE
resolve_damage_pvp = 解析伤害PVP
