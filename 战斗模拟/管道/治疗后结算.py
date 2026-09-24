"""治疗后结算编排 stub：受疗方回血 → [PVE 治疗仇恨] → 收束。

设计层 SSOT 在框架表「战斗流程」治疗后结算*。
- 调用结算(回血,治疗值)：结算主体重映射为受疗方（该次管线 **守方**=受疗目标）
- 调用结算(治疗仇恨,治疗值)：仅 PVE
- 吸血禁止再入本编排 / 治疗*（吸血走命中后结算→回血*；彼处攻方→该次守方）
"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.注册表 import 注册
from 战斗模拟.管道 import 扣血 as hp_mod


def _f(ctx: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in ctx and ctx[k] is not None:
            try:
                return float(ctx[k])
            except (TypeError, ValueError):
                pass
    return float(default)


def _apply_post_heal(ctx: dict[str, Any], *, 模式: str) -> dict[str, Any]:
    out = dict(ctx)
    log: list[str] = []
    heal = _f(out, "治疗值", "heal")

    heal_ctx = dict(out)
    heal_ctx["治疗值"] = heal
    # 结算主体 = 受疗方 = 守方
    if "守方" not in heal_ctx and "生命值" in out:
        heal_ctx["守方"] = {"生命值": _f(out, "生命值")}
    heal_res = (
        hp_mod.解析回血PVE(heal_ctx) if 模式 == "PVE" else hp_mod.解析回血PVP(heal_ctx)
    )
    log.append("受疗方执行回血")
    out["受疗方回血"] = heal_res
    out["当前生命"] = heal_res.get("当前生命", out.get("当前生命"))
    out["实际治疗"] = heal_res.get("实际治疗")
    out["过量治疗"] = heal_res.get("过量治疗")

    if 模式 == "PVE":
        log.append("写入治疗仇恨")
        out["治疗仇恨_stub"] = heal
        log.append("治疗编排收束")
    else:
        log.append("治疗编排收束")

    out.update({"模式": 模式, "管线": f"治疗后结算{模式}", "阶段日志": log})
    return out


def 解析治疗后结算PVE(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_post_heal(c, 模式="PVE")


def 解析治疗后结算PVP(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_post_heal(c, 模式="PVP")


注册("治疗后结算PVE", 解析治疗后结算PVE)
注册("治疗后结算PVP", 解析治疗后结算PVP)
注册("post_heal_pve", 解析治疗后结算PVE)
注册("post_heal_pvp", 解析治疗后结算PVP)
