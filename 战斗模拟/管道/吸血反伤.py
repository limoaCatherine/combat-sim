"""吸血反伤算量 helper（方案 β）— 已内联进「伤害*」主管线，非独立流程块。

设计层 SSOT：战斗流程 伤害PVE/PVP 步骤 20–32（内联通道选择）。
本模块保留可调用薄封装供回归；勿再把「吸血反伤*」当作 sheet 独立块。
面板 → 对应* → 量：
  物理 → 攻方(物理吸血%) / 守方(物理反伤%)
  魔法 → 攻方(魔法吸血%) / 守方(魔法反伤%)
再叠加 全能吸血% / 全能反伤%；量 = 最终伤害 * (对应 + 全能)。
零伤/已闪避短路清零。
"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.注册表 import 注册


def _f(ctx: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in ctx and ctx[k] is not None:
            try:
                return float(ctx[k])
            except (TypeError, ValueError):
                pass
    return float(default)


def _side_attr(side: Any, *names: str, default: float = 0.0) -> float:
    if isinstance(side, dict):
        return _f(side, *names, default=default)
    return float(default)


def 对应通道比例(
    伤害类型: str,
    *,
    物理: float,
    魔法: float,
) -> float:
    """物理/魔法取对应通道面板。"""
    kind = str(伤害类型 or "").strip()
    if kind == "物理":
        return float(物理)
    if kind == "魔法":
        return float(魔法)
    return 0.0


def _calc(ctx: dict[str, Any], *, 模式: str) -> dict[str, Any]:
    out = dict(ctx)
    final_dmg = _f(out, "最终伤害", "finalDamage")
    dodged = bool(out.get("已闪避") or out.get("标记_已闪避"))
    marks = out.get("标记") or out.get("marks") or ()
    if isinstance(marks, str):
        marks = (marks,)
    if any(str(t) == "已闪避" for t in marks):
        dodged = True

    if final_dmg <= 0 or dodged:
        out.update(
            {
                "对应吸血": 0.0,
                "对应反伤": 0.0,
                "吸血量": 0.0,
                "反伤量": 0.0,
                "模式": 模式,
                "管线": f"吸血反伤{模式}",
                "阶段日志": ["判定零伤短路", "清零吸血量", "清零反伤量"],
            }
        )
        return out

    kind = str(out.get("伤害类型") or out.get("damage_kind") or "物理")
    atk = out.get("攻方") if isinstance(out.get("攻方"), dict) else out
    dfn = out.get("守方") if isinstance(out.get("守方"), dict) else out

    corr_ls = 对应通道比例(
        kind,
        物理=_side_attr(atk, "物理吸血%", "PhysLS", default=_f(out, "物理吸血%")),
        魔法=_side_attr(atk, "魔法吸血%", "MagLS", default=_f(out, "魔法吸血%")),
    )
    corr_rf = 对应通道比例(
        kind,
        物理=_side_attr(dfn, "物理反伤%", "PhysReflect", default=_f(out, "物理反伤%")),
        魔法=_side_attr(dfn, "魔法反伤%", "MagReflect", default=_f(out, "魔法反伤%")),
    )
    omni_ls = _side_attr(atk, "全能吸血%", "LifeSteal", default=_f(out, "全能吸血%"))
    omni_rf = _side_attr(dfn, "全能反伤%", "Reflect", default=_f(out, "全能反伤%"))

    ls = final_dmg * (corr_ls + omni_ls)
    rf = final_dmg * (corr_rf + omni_rf)
    out.update(
        {
            "对应吸血": corr_ls,
            "对应反伤": corr_rf,
            "吸血量": ls,
            "反伤量": rf,
            "模式": 模式,
            "管线": f"吸血反伤{模式}",
            "阶段日志": [
                "判定零伤短路",
                "判定物理通道" if kind == "物理" else "判定魔法通道",
                "计算吸血量",
                "计算反伤量",
            ],
        }
    )
    return out


def 解析吸血反伤PVE(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _calc(c, 模式="PVE")


def 解析吸血反伤PVP(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _calc(c, 模式="PVP")


注册("吸血反伤PVE", 解析吸血反伤PVE)
注册("吸血反伤PVP", 解析吸血反伤PVP)
注册("lifesteal_reflect_pve", 解析吸血反伤PVE)
注册("lifesteal_reflect_pvp", 解析吸血反伤PVP)
