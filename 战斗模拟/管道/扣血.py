"""扣血 / 回血可调用助手：与解释器共用 管道/护盾吸收.py FIFO 核心。

设计层 SSOT 在框架表「战斗流程」伤害PVE/PVP 内联【扣血段】（独立 扣血PVE/PVP
sheet 块已删除，勿再引入）。运行时权威路径是 sheet 驱动解释器；本模块的
解析扣血PVE/PVP 是同一 FIFO 语义的可调用助手，供引擎回退、单测与批跑使用。

主路径顺序（UGit 底 + MMO 扩展）：
  物/魔免疫 || 无敌 → 护盾 FIFO（容量+次数）→ 扣生命（锁1血）
  → 过量/死亡 → …；回血：治疗吸收 → 夹断 → 过量 → [过量转盾]
"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.护盾吸收 import (
    fifo_护盾吸收,
    fifo_治疗吸收,
    执行过量转盾,
    执行破盾结束Buff,
)
from 战斗模拟.管道.注册表 import 注册


def _f(ctx: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in ctx and ctx[k] is not None:
            try:
                return float(ctx[k])
            except (TypeError, ValueError):
                pass
    return float(default)


def _status_bag(ctx: dict[str, Any]) -> set[str]:
    bag: set[str] = set()
    for key in ("无敌", "锁1血", "defender_is_invulnerable"):
        if ctx.get(key):
            bag.add("无敌" if key == "defender_is_invulnerable" else key)
    statuses = ctx.get("状态") or ctx.get("statuses") or ()
    if isinstance(statuses, str):
        statuses = (statuses,)
    for t in statuses:
        bag.add(str(t))
    side = ctx.get("守方") or ctx.get("defender") or {}
    if isinstance(side, dict):
        st = side.get("状态") or side.get("statuses") or ()
        if isinstance(st, str):
            st = (st,)
        for t in st:
            bag.add(str(t))
        tags = side.get("标签") or ()
        if isinstance(tags, (set, list, tuple)):
            for t in tags:
                bag.add(str(t))
    # 结算目标侧
    role = ctx.get("结算目标") or "守方"
    settle = ctx.get(role)
    if isinstance(settle, dict) and settle is not side:
        st = settle.get("状态") or settle.get("statuses") or ()
        if isinstance(st, str):
            st = (st,)
        for t in st:
            bag.add(str(t))
    return bag


def _has_invuln(ctx: dict[str, Any]) -> bool:
    """泛无敌：状态/标记「无敌」→ 伤害落地前归零。"""
    if "无敌" in _status_bag(ctx):
        return True
    return _has_mark(ctx, "无敌")


def _has_lock1(ctx: dict[str, Any]) -> bool:
    if "锁1血" in _status_bag(ctx):
        return True
    return _has_mark(ctx, "锁1血")


def _has_type_immune(ctx: dict[str, Any], kind: str) -> bool:
    """UGit：IMMUNE_PHYSICAL / IMMUNE_MAGIC 异常。"""
    bag = _status_bag(ctx)
    k = str(kind or "").strip()
    if k in ("物理", "物理伤害") and (
        "免疫物理" in bag or "IMMUNE_PHYSICAL" in bag
    ):
        return True
    if k in ("魔法", "魔法伤害") and (
        "免疫魔法" in bag or "IMMUNE_MAGIC" in bag
    ):
        return True
    return False


def _has_mark(ctx: dict[str, Any], name: str) -> bool:
    if ctx.get(name) or ctx.get(f"标记_{name}"):
        return True
    marks = ctx.get("标记") or ctx.get("marks") or ()
    if isinstance(marks, str):
        marks = (marks,)
    return any(str(t) == name for t in marks)


def _zero_settle(out: dict[str, Any], *, 模式: str, log: list[str]) -> dict[str, Any]:
    out["结算伤害"] = 0.0
    out["护盾吸收量"] = 0.0
    out["过量伤害"] = 0.0
    out["本次破盾数"] = 0.0
    out["实际扣血"] = 0.0
    out["已死亡"] = False
    out["已破盾"] = False
    out.update({"模式": 模式, "管线": f"扣血{模式}", "阶段日志": log})
    return out


def _apply_扣血(ctx: dict[str, Any], *, 模式: str) -> dict[str, Any]:
    """顺序：物魔免疫/无敌→护盾FIFO(含次数)→破盾→过量→夹断→扣生命→锁1血→死亡。"""
    out = dict(ctx)
    log: list[str] = []
    kind = str(out.get("伤害类型") or out.get("damage_kind") or "物理")

    if _has_type_immune(out, kind):
        log.extend(["判定物魔免疫", "免疫清零结算", "扣血收束"])
        return _zero_settle(out, 模式=模式, log=log)

    if _has_invuln(out):
        log.extend(["判定无敌", "无敌清零结算", "扣血收束"])
        return _zero_settle(out, 模式=模式, log=log)

    log.append("判定物魔免疫")
    log.append("判定无敌")
    if _has_mark(out, "结算伤害已注入") and out.get("结算伤害") is not None:
        try:
            dmg = float(out["结算伤害"])
        except (TypeError, ValueError):
            dmg = _f(out, "最终伤害", "finalDamage")
        log.extend(["判定结算伤害已注入", "执行护盾吸收"])
    else:
        dmg = _f(out, "最终伤害", "finalDamage")
        out["结算伤害"] = dmg
        log.extend(["判定结算伤害已注入", "初始化结算伤害", "执行护盾吸收"])

    out["结算伤害"] = dmg

    absorbed = 0.0
    broken = 0
    broken_list: list[dict[str, Any]] = []
    if (
        "护盾吸收量" in out
        and out["护盾吸收量"] is not None
        and "shields" not in out
        and "护盾列表" not in out
        and "护盾层" not in out
    ):
        absorbed = max(0.0, _f(out, "护盾吸收量"))
        dmg = max(0.0, dmg - absorbed)
    else:
        shields = list(out.get("shields") or out.get("护盾列表") or out.get("护盾层") or [])
        if shields:
            dmg, absorbed, broken, alive = fifo_护盾吸收(
                shields, dmg, kind, out_broken=broken_list
            )
            out["shields"] = alive
            out["护盾列表"] = alive
            out["护盾层"] = alive
            if broken_list:
                执行破盾结束Buff(out, broken_list)
        else:
            absorbed = 0.0
            dmg = max(0.0, dmg)

    out["护盾吸收量"] = absorbed
    out["结算伤害"] = dmg
    out["本次破盾数"] = broken
    out["已破盾"] = broken > 0
    log.append("结算溢出伤害")
    if broken > 0:
        log.extend(["判定破盾", "标记破盾"])
    else:
        log.append("判定破盾")

    hp = _f(out, "当前生命", "hp", "结算目标生命", "生命")
    raw_for_overkill = dmg
    overkill = max(0.0, raw_for_overkill - hp)
    dmg = min(dmg, max(hp, 0.0))
    new_hp = max(0.0, hp - dmg)
    dead = new_hp <= 0.0

    if _has_lock1(out):
        log.append("判定锁1血")
        if new_hp < 1.0 and hp >= 1.0:
            # 免死雏形：扣后至少留 1
            new_hp = 1.0
            dmg = max(0.0, hp - 1.0)
            overkill = max(0.0, raw_for_overkill - (hp - 1.0))
            dead = False
            log.append("应用锁1血")
        elif new_hp < 1.0:
            new_hp = 1.0
            dmg = 0.0
            overkill = 0.0
            dead = False
            log.append("应用锁1血")

    out.update(
        {
            "过量伤害": overkill,
            "结算伤害": dmg,
            "实际扣血": dmg,
            "当前生命": new_hp,
            "结算目标生命": new_hp,
            "已死亡": dead,
            "模式": 模式,
            "管线": f"扣血{模式}",
        }
    )
    log.extend(["记录过量伤害", "夹断扣血量", "执行扣血", "判定死亡"])
    log.append("标记死亡" if dead else "扣血收束")
    out["阶段日志"] = log
    return out


def _apply_回血(ctx: dict[str, Any], *, 模式: str) -> dict[str, Any]:
    """治疗吸收 → 空档夹断 → 记录过量 → 执行回血 → [过量转盾]。"""
    hp = _f(ctx, "当前生命", "hp")
    heal = _f(ctx, "治疗值", "heal", "治疗量")
    hp_max = _f(ctx, "生命值", "守方生命值", "hp_max", default=0.0)
    if hp_max <= 0 and "守方" in ctx and isinstance(ctx["守方"], dict):
        hp_max = _f(ctx["守方"], "生命值", default=0.0)

    out = dict(ctx)
    log = [
        "执行治疗吸收",
    ]

    # 治疗吸收 FIFO
    absorb_layers = list(
        out.get("治疗吸收层")
        or (out.get("守方") or {}).get("治疗吸收层")
        or []
    )
    heal_absorbed = 0.0
    if absorb_layers:
        heal, heal_absorbed, _brk, alive = fifo_治疗吸收(absorb_layers, heal)
        out["治疗吸收层"] = alive
        side = out.get("结算目标") and out.get(out.get("结算目标")) or out.get("守方")
        if isinstance(side, dict):
            side["治疗吸收层"] = alive
    out["治疗吸收量"] = heal_absorbed
    out["治疗量"] = heal
    out["治疗值"] = heal

    room = max(0.0, hp_max - hp) if hp_max > 0 else max(0.0, heal)
    if hp_max > 0:
        actual = min(heal, room)
    else:
        actual = max(0.0, heal)
        room = actual
    overheal = max(0.0, heal - actual)
    new_hp = hp + actual
    if hp_max > 0:
        new_hp = min(new_hp, hp_max)
    out.update(
        {
            "生命空档": room if hp_max > 0 else max(0.0, heal),
            "实际治疗": actual,
            "过量治疗": overheal,
            "溢出治疗": overheal,
            "当前生命": new_hp,
            "模式": 模式,
            "管线": f"回血{模式}",
            "阶段日志": log
            + [
                "计算生命空档",
                "夹断实际治疗",
                "记录过量治疗",
                "执行回血",
                "回血收束",
            ],
        }
    )
    if _has_mark(out, "过量转盾开启") and overheal > 1e-9:
        out["过量转盾量"] = overheal
        执行过量转盾(out)
        lg = list(out.get("阶段日志") or [])
        lg.insert(-1, "过量转化护盾")
        out["阶段日志"] = lg
    else:
        out["过量转盾量"] = 0.0
    return out


def 解析扣血PVE(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_扣血(c, 模式="PVE")


def 解析扣血PVP(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_扣血(c, 模式="PVP")


def 解析回血PVE(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_回血(c, 模式="PVE")


def 解析回血PVP(ctx: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    c = dict(ctx or {})
    c.update(extra)
    return _apply_回血(c, 模式="PVP")


注册("扣血PVE", 解析扣血PVE)
注册("扣血PVP", 解析扣血PVP)
注册("回血PVE", 解析回血PVE)
注册("回血PVP", 解析回血PVP)
注册("hp_damage_pve", 解析扣血PVE)
注册("hp_damage_pvp", 解析扣血PVP)
注册("hp_heal_pve", 解析回血PVE)
注册("hp_heal_pvp", 解析回血PVP)
