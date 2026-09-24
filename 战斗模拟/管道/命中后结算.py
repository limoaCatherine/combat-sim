"""命中后结算编排 stub：闪避门 → 守方扣血 → 吸血(攻方回血) → 反伤(攻方扣血) → [PVE仇恨门]。

设计层 SSOT 在框架表「战斗流程」命中后结算*；算量管线产出 最终伤害/吸血量/反伤量。
语义：
- 调用结算(扣血,X[,伤害类型])：写入结算伤害=X + 标记(结算伤害已注入)；可选覆盖伤害类型；
  结算主体重映射为该次管线的「守方」
- 调用结算(回血,X)：跑回血*，治疗值=X（吸血不经治疗*：无施法治疗/受治疗/治疗暴击）
- 调用结算(伤害仇恨,...)：既有伤害仇恨PVE；反伤杀死攻方后跳过（有标记(攻方已死亡)）
- 顺序对齐 legacy：守方扣血 → 吸血 → 反伤（攻方可先回血再吃反伤）
- 反伤扣血继承当前命中上下文的 伤害类型（与原技能相同）；不重跑伤害*
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


def _has_mark(ctx: dict[str, Any], name: str) -> bool:
    if ctx.get(name) or ctx.get(f"标记_{name}"):
        return True
    marks = ctx.get("标记") or ctx.get("marks") or ()
    if isinstance(marks, str):
        marks = (marks,)
    return any(str(t) == name for t in marks)


def _add_mark(ctx: dict[str, Any], name: str) -> None:
    ctx[name] = True
    marks = list(ctx.get("标记") or ctx.get("marks") or [])
    if isinstance(ctx.get("标记"), str):
        marks = [ctx["标记"]]
    if name not in marks:
        marks.append(name)
    ctx["标记"] = marks


def _attacker_hp_ctx(out: dict[str, Any]) -> tuple[float, float]:
    """Return (当前生命, 生命值上限) for attacker side."""
    atk_hp = _f(out, "攻方当前生命", "attacker_hp", default=0.0)
    if isinstance(out.get("攻方"), dict):
        atk_hp = _f(out["攻方"], "当前生命", "hp", default=atk_hp)
    if "攻方吸血回血" in out:
        atk_hp = _f(out["攻方吸血回血"], "当前生命", default=atk_hp)
    hp_max = _f(out, "攻方生命值", "attacker_hp_max", default=0.0)
    if isinstance(out.get("攻方"), dict):
        hp_max = _f(out["攻方"], "生命值", "hp_max", default=hp_max)
    return atk_hp, hp_max


def _settle_扣血(
    amount: float,
    *,
    模式: str,
    base: dict[str, Any],
    伤害类型: str | None = None,
) -> dict[str, Any]:
    """调用结算(扣血,量[,伤害类型])：注入结算伤害 + 标记(结算伤害已注入)。"""
    ctx = dict(base)
    ctx["结算伤害"] = float(amount)
    _add_mark(ctx, "结算伤害已注入")
    if 伤害类型 is not None:
        ctx["伤害类型"] = 伤害类型
        ctx["damage_kind"] = 伤害类型
    return hp_mod.解析扣血PVE(ctx) if 模式 == "PVE" else hp_mod.解析扣血PVP(ctx)


def _apply_post_hit(ctx: dict[str, Any], *, 模式: str) -> dict[str, Any]:
    out = dict(ctx)
    log: list[str] = ["判定已闪避"]
    if _has_mark(out, "已闪避"):
        log.append("结算编排收束")
        out.update({"模式": 模式, "管线": f"命中后结算{模式}", "阶段日志": log, "跳过结算": True})
        return out

    final_dmg = _f(out, "最终伤害", "finalDamage")
    reflect = _f(out, "反伤量", "反伤", "reflectDamage")
    lifesteal = _f(out, "吸血量", "吸血", "lifesteal")
    dmg_kind = str(out.get("伤害类型") or out.get("damage_kind") or "物理")

    # 守方扣血（结算伤害=最终伤害；结算主体=原守方）
    def_res = _settle_扣血(final_dmg, 模式=模式, base=out, 伤害类型=dmg_kind)
    log.append("守方执行扣血")
    out["守方扣血"] = def_res
    out["当前生命"] = def_res.get("当前生命", out.get("当前生命"))
    out["已死亡"] = def_res.get("已死亡", False)

    # 吸血 → 攻方回血（不经治疗* / 治疗暴击 / HealPct）；结算主体重映射为攻方=守方
    if lifesteal > 0:
        atk_hp, hp_max = _attacker_hp_ctx(out)
        heal_ctx = {
            "当前生命": atk_hp,
            "治疗值": lifesteal,
            "生命值": hp_max,
            "守方": {"生命值": hp_max},
        }
        heal_res = (
            hp_mod.解析回血PVE(heal_ctx) if 模式 == "PVE" else hp_mod.解析回血PVP(heal_ctx)
        )
        log.extend(["判定吸血", "攻方执行吸血回血"])
        out["攻方吸血回血"] = heal_res
    else:
        log.append("判定吸血")

    # 反伤 → 攻方扣血（继承伤害类型；注入门）
    attacker_dead = False
    if reflect > 0:
        atk_hp, _hp_max = _attacker_hp_ctx(out)
        if "攻方吸血回血" in out:
            atk_hp = _f(out["攻方吸血回血"], "当前生命", default=atk_hp)
        atk_ctx: dict[str, Any] = {
            "当前生命": atk_hp if atk_hp > 0 else _f(out, "攻方", default=0.0) or 0.0,
            "伤害类型": dmg_kind,
            "shields": out.get("攻方护盾") or out.get("attacker_shields") or [],
            "无敌": out.get("攻方无敌") or False,
        }
        if isinstance(out.get("攻方"), dict):
            atk_side = out["攻方"]
            if "攻方吸血回血" not in out:
                atk_ctx["当前生命"] = _f(atk_side, "当前生命", "hp", default=atk_ctx["当前生命"])
            atk_ctx["无敌"] = bool(atk_side.get("无敌"))
            if "shields" in atk_side:
                atk_ctx["shields"] = atk_side["shields"]
        atk_res = _settle_扣血(reflect, 模式=模式, base=atk_ctx, 伤害类型=dmg_kind)
        log.extend(["判定反伤", "攻方执行反伤扣血"])
        out["攻方反伤扣血"] = atk_res
        attacker_dead = bool(atk_res.get("已死亡", False))
        out["攻方已死亡"] = attacker_dead
        if attacker_dead:
            _add_mark(out, "攻方已死亡")
            # also mirror settle-subject 已死亡 for engines that only read 已死亡 on sub-ctx
            out["攻方反伤扣血"]["攻方已死亡"] = True
    else:
        log.append("判定反伤")

    if 模式 == "PVE":
        log.append("判定攻方已死亡")
        if attacker_dead or _has_mark(out, "攻方已死亡"):
            log.append("跳过仇恨收束")
            out.update({"模式": 模式, "管线": f"命中后结算{模式}", "阶段日志": log, "跳过仇恨": True})
            return out
        log.append("写入伤害仇恨")
        out["伤害仇恨_stub"] = final_dmg  # 编排层仅记录；正式仇恨管线另算
        log.append("结算编排收束")
    else:
        log.append("结算编排收束")

    out.update({"模式": 模式, "管线": f"命中后结算{模式}", "阶段日志": log})
    return out


def 解析命中后结算PVE(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_post_hit(c, 模式="PVE")


def 解析命中后结算PVP(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_post_hit(c, 模式="PVP")


注册("命中后结算PVE", 解析命中后结算PVE)
注册("命中后结算PVP", 解析命中后结算PVP)
注册("post_hit_pve", 解析命中后结算PVE)
注册("post_hit_pvp", 解析命中后结算PVP)
