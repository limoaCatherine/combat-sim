"""技能驱动 DES 引擎：GCD/CD/吟唱/动作 + 状态依赖 1-ply 择技 + 伤害/治疗管线。

主路径为真实 MC（期望模式=False，RNG 掷命中/暴击/格挡等）。
择技：感知快照 → 1-ply 状态路径价值 → 执行；APL 仅作弱偏置。
期望模式仅供独立 EV 分析，不得作为默认战斗路径。
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from 战斗模拟.内核.事件 import (
    KIND_CAST_COMPLETE,
    KIND_IMPACT,
    KIND_TICK,
    事件,
    事件调度器,
)
from 战斗模拟.内核.引擎 import 战斗引擎, 战斗结果, _实体转面板
from 战斗模拟.模型.实体 import 实体
from 战斗模拟.世界 import 世界数据
from 战斗模拟.领域.面板表达式 import 切段, 求值
from 战斗模拟.ai.技能价值 import 感知快照, 选技_1ply

KIND_DECIDE = "DECIDE"
KIND_BUFF_EXPIRE = "BUFF_EXPIRE"

_MOD_RE = re.compile(
    r"(?P<attr>[^\s+\-*/0-9%]+)\s*(?P<op>[+\-])\s*(?P<val>\d+(?:\.\d+)?)\s*(?P<pct>%?)"
)


@dataclass
class _运行技:
    编号: str
    名称: str
    等级: int
    栏位序: int
    apl: float
    伤害段: str
    治疗解析式: str
    冷却毫秒: float
    吟唱毫秒: float
    动作毫秒: float
    公共冷却毫秒: float
    占用GCD: bool
    仇恨系数: float
    段期望系数: float
    数值类型: str
    效果绑定: str  # 状态代号，可空
    效果等级: int | None
    命中位: str = ""
    cd_ready_at: float = 0.0


@dataclass
class _运行体:
    实体: 实体
    技能: list[_运行技] = field(default_factory=list)
    gcd_ready_at: float = 0.0
    busy_until: float = 0.0
    casting: bool = False
    伤害总量: float = 0.0
    治疗总量: float = 0.0
    技能伤害: dict[str, float] = field(default_factory=dict)
    技能治疗: dict[str, float] = field(default_factory=dict)
    施法次数: dict[str, int] = field(default_factory=dict)
    gcd_占用毫秒: float = 0.0
    buffs: dict[str, dict[str, Any]] = field(default_factory=dict)


def _panel_dict(e: 实体) -> dict[str, Any]:
    return _实体转面板(e)


def _effective_panel(actor: _运行体) -> dict[str, Any]:
    """基础面板 + 薄 buff 修正（受伤±%、属性±绝对值/百分比）。"""
    base = dict(_panel_dict(actor.实体))
    for _bn, b in actor.buffs.items():
        for mod in b.get("mods") or []:
            attr = mod["attr"]
            if mod.get("pct"):
                cur = float(base.get(attr) or 0.0)
                if mod["op"] == "+":
                    base[attr] = cur * (1.0 + mod["val"] / 100.0)
                else:
                    base[attr] = cur * (1.0 - mod["val"] / 100.0)
            else:
                cur = float(base.get(attr) or 0.0)
                base[attr] = cur + (mod["val"] if mod["op"] == "+" else -mod["val"])
    return base


def _parse_mods(expr: str) -> list[dict[str, Any]]:
    if not expr or str(expr).strip() in ("", "无", "—"):
        return []
    out: list[dict[str, Any]] = []
    for part in re.split(r"[;；,，]", str(expr)):
        part = part.strip()
        if not part:
            continue
        m = _MOD_RE.search(part)
        if not m:
            continue
        out.append(
            {
                "attr": m.group("attr").strip(),
                "op": m.group("op"),
                "val": float(m.group("val")),
                "pct": bool(m.group("pct")),
            }
        )
    return out


def _apl_key(raw: Any, bar_index: int) -> float:
    if raw is None or str(raw).strip() in ("", "—", "-"):
        return float(-bar_index)  # 无 APL：靠前栏位略高
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(-bar_index)


def _ms(v: Any, default: float) -> float:
    if v is None or str(v).strip() in ("", "—", "-", "无"):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _取面板(world: 世界数据, 构筑名: str) -> tuple[dict[str, float], int]:
    """返回 (属性dict, 等级)。优先流派面板，再怪物面板。"""
    attrs: dict[str, float] = {}
    sm = world.标准模型
    if sm and 构筑名 in sm.面板:
        for k, v in sm.面板[构筑名].属性.items():
            if v is not None:
                try:
                    attrs[k] = float(v)
                except (TypeError, ValueError):
                    pass
    builds = world.构筑
    if builds and hasattr(builds, "怪物面板") and 构筑名 in builds.怪物面板:
        for k, v in builds.怪物面板[构筑名].属性.items():
            if v is not None and k not in attrs:
                try:
                    attrs[k] = float(v)
                except (TypeError, ValueError):
                    pass
            elif v is not None and 构筑名 not in (sm.面板 if sm else {}):
                try:
                    attrs[k] = float(v)
                except (TypeError, ValueError):
                    pass
    # 若流派未命中但怪物有，用怪物全量
    if not attrs and builds and 构筑名 in getattr(builds, "怪物面板", {}):
        for k, v in builds.怪物面板[构筑名].属性.items():
            if v is not None:
                try:
                    attrs[k] = float(v)
                except (TypeError, ValueError):
                    pass
    if "等级" not in attrs:
        raise ValueError(f"{构筑名} 缺少等级缓存，禁止默认 60")
    level = int(attrs["等级"])
    if level <= 0:
        raise ValueError(f"{构筑名} 等级非法: {level}")
    return attrs, level


def _建实体(world: 世界数据, 构筑名: str, *, 阵营: str, eid: str) -> 实体:
    attrs, level = _取面板(world, 构筑名)
    hp = attrs.get("生命值")
    if not isinstance(hp, (int, float)) or float(hp) <= 0:
        raise ValueError(f"{构筑名} 缺少生命值缓存，禁止默认生命")
    hp = float(hp)
    panel = dict(attrs)
    return 实体(
        id=eid,
        名称=构筑名,
        阵营=阵营,
        等级=level,
        生命=hp,
        生命上限=hp,
        面板=panel,
        标签={"木桩"} if 构筑名 == "木桩" else set(),
    )


def 诊断技能栏(world: 世界数据, 构筑名: str) -> dict[str, Any]:
    runnable, skips = _解析技能列表(world, 构筑名, 收集跳过=True)
    return {
        "构筑": 构筑名,
        "可跑数": len(runnable),
        "可跑": [s.名称 for s in runnable],
        "跳过": skips,
    }


def _解析技能列表(
    world: 世界数据, 构筑名: str, *, 收集跳过: bool = False
):
    builds = getattr(world, "构筑", None)
    skill_cat = getattr(world, "技能目录", None)
    skill_lv = getattr(world, "技能等级", None)
    out: list[_运行技] = []
    skips: list[dict[str, str]] = []
    if not builds or 构筑名 not in getattr(builds, "按名", {}):
        if 收集跳过:
            return out, [{"技能": "", "原因": "构筑配置无此名"}]
        return out
    bdef = builds.按名[构筑名]
    for slot in bdef.技能栏:
        name = slot.技能名
        lv = slot.等级
        if lv is None:
            skips.append({"技能": name, "原因": "构筑配置无技能等级"})
            continue
        sdef = None
        if skill_cat:
            if name in skill_cat.按编号:
                sdef = skill_cat.按编号[name]
            else:
                for s in skill_cat.按编号.values():
                    if s.名称 == name or s.编号 == name:
                        sdef = s
                        break
        lv_row = None
        if skill_lv:
            try:
                lv_row = skill_lv.取(name, lv)
            except Exception:  # noqa: BLE001
                lv_row = None
        dmg = (lv_row.伤害段 if lv_row else "") or ""
        heal = (lv_row.治疗解析式 if lv_row else "") or ""
        if not dmg and not heal:
            skips.append({"技能": name, "原因": "技能总表无伤害段且无治疗解析式"})
            continue
        cd = _ms(lv_row.冷却 if lv_row else None, _ms(getattr(sdef, "原始行", {}).get("冷却时间") if sdef else None, 0.0))
        if sdef and lv_row and lv_row.冷却 is None:
            cd = _ms(sdef.原始行.get("冷却时间"), cd)
        cast = _ms(lv_row.吟唱 if lv_row else None, 0.0)
        if sdef and (lv_row is None or lv_row.吟唱 is None):
            cast = _ms(sdef.原始行.get("吟唱时长"), cast)
        action_raw = lv_row.动作 if lv_row else None
        if action_raw is None and sdef:
            action_raw = sdef.原始行.get("动作时长")
        gcd_raw = lv_row.公共冷却 if lv_row else None
        if gcd_raw is None and sdef:
            gcd_raw = sdef.原始行.get("公共冷却时长")
        if action_raw is None or str(action_raw).strip() in ("", "—", "-", "无"):
            skips.append({"技能": name, "原因": "无动作时长毫秒"})
            continue
        if gcd_raw is None or str(gcd_raw).strip() in ("", "—", "-", "无"):
            skips.append({"技能": name, "原因": "无公共冷却时长毫秒"})
            continue
        action = float(action_raw)
        gcd = float(gcd_raw)
        threat = 1.0
        if lv_row and lv_row.仇恨系数 is not None:
            threat = float(lv_row.仇恨系数)
        elif sdef and sdef.仇恨系数 is not None:
            threat = float(sdef.仇恨系数)
        occupy = True
        if sdef and str(sdef.占用GCD).strip() in ("否", "N", "n", "false", "0"):
            occupy = False
        dtype = str(sdef.数值类型).strip() if sdef and sdef.数值类型 else ""
        if not dtype:
            skips.append({"技能": name, "原因": "无数值类型"})
            continue
        hit_pos = ""
        if sdef:
            hit_pos = str(sdef.原始行.get("命中位") or "").strip()
            if hit_pos in ("—", "-", "无"):
                hit_pos = ""
        if not hit_pos:
            skips.append({"技能": name, "原因": "无命中位"})
            continue
        eff_code = ""
        if sdef:
            eff_code = str(sdef.原始行.get("施加效果1") or "").strip()
            if eff_code in ("—", "-", "无"):
                eff_code = ""
        eff_lv = lv_row.效果等级 if lv_row and lv_row.效果等级 is not None else lv
        seg_c = float(lv_row.段期望系数) if lv_row else 1.0
        code = sdef.编号 if sdef else name
        apl = _apl_key(sdef.APL优先级 if sdef else None, slot.槽位)
        out.append(
            _运行技(
                编号=code,
                名称=name,
                等级=lv,
                栏位序=slot.槽位,
                apl=apl,
                伤害段=dmg,
                治疗解析式=heal,
                冷却毫秒=cd,
                吟唱毫秒=cast,
                动作毫秒=action,
                公共冷却毫秒=gcd,
                占用GCD=occupy,
                仇恨系数=threat,
                段期望系数=seg_c,
                数值类型=dtype,
                效果绑定=eff_code,
                效果等级=eff_lv,
                命中位=hit_pos,
            )
        )
    if 收集跳过:
        return out, skips
    return out


class 技能战斗引擎:
    """真实多动作 DES：技能择技 → 吟唱/动作/GCD → 命中结算。"""

    def __init__(
        self,
        world: 世界数据,
        *,
        攻方构筑: str,
        守方构筑: str = "木桩",
        上限毫秒: float | None = None,
        期望模式: bool = False,
        强制命中: bool = False,
        模式: str = "PVE",
    ) -> None:
        self.world = world
        self.攻方构筑 = 攻方构筑
        self.守方构筑 = 守方构筑
        if 上限毫秒 is None:
            raise ValueError("上限毫秒必须来自场景战斗时长秒，禁止默认 30s")
        self.上限毫秒 = float(上限毫秒)
        self.期望模式 = 期望模式
        self.强制命中 = 强制命中
        self.模式 = 模式.upper() if 模式 else "PVE"
        self.调度器 = 事件调度器()
        self.sample: list[dict[str, Any]] = []
        path = getattr(world, "路径", None)
        if path is None:
            raise ValueError("技能战斗引擎需要世界.路径以加载战斗流程")
        self._结算 = 战斗引擎(
            world=world,
            工作簿路径=path,
            基础伤害=None,
            模式=self.模式,
            加载触发表=False,
            心跳=False,
        )

    def run_once(self, *, seed: int = 0) -> 战斗结果:
        rng = random.Random(seed)
        atk_e = _建实体(self.world, self.攻方构筑, 阵营="友方", eid="A")
        dfd_e = _建实体(self.world, self.守方构筑, 阵营="敌方", eid="B")
        atk = _运行体(实体=atk_e, 技能=_解析技能列表(self.world, self.攻方构筑))
        dfd = _运行体(实体=dfd_e, 技能=_解析技能列表(self.world, self.守方构筑))
        # 木桩通常无主动技能
        actors = {"A": atk, "B": dfd}

        self.调度器.清空()
        self.sample = []
        # 决策心跳：攻方从 0 开始；守方若有技能也从 0
        self.调度器.调度(0.0, KIND_DECIDE, {"actor": "A"})
        if dfd.技能:
            self.调度器.调度(0.0, KIND_DECIDE, {"actor": "B"})

        事件数 = 0
        self._结算._rng = rng
        max_events = 200_000

        while True:
            ev = self.调度器.推进()
            if ev is None:
                break
            事件数 += 1
            now = self.调度器.现在毫秒
            if now > self.上限毫秒 + 1e-6:
                break
            if 事件数 > max_events:
                break
            if not dfd.实体.存活 or not atk.实体.存活:
                break

            kind = ev.种类
            payload = ev.载荷

            if kind == KIND_DECIDE:
                aid = payload.get("actor", "A")
                self._decide(aid, actors, now)
            elif kind == KIND_CAST_COMPLETE:
                self._on_cast_complete(payload, actors, now)
            elif kind == KIND_IMPACT:
                self._on_impact(payload, actors, now)
            elif kind == KIND_BUFF_EXPIRE:
                aid = payload.get("actor")
                bn = payload.get("buff")
                if aid in actors and bn in actors[aid].buffs:
                    del actors[aid].buffs[bn]
            elif kind == KIND_TICK:
                pass

            if not dfd.实体.存活 or not atk.实体.存活:
                break
            if now >= self.上限毫秒:
                break

        duration = min(self.调度器.现在毫秒, self.上限毫秒)
        if duration <= 0:
            duration = self.上限毫秒
        total_dmg = atk.伤害总量
        total_heal = atk.治疗总量
        dps = total_dmg / (duration / 1000.0) if duration > 0 else 0.0
        hps = total_heal / (duration / 1000.0) if duration > 0 else 0.0
        ttk = None
        if not dfd.实体.存活:
            ttk = duration / 1000.0
        gcd_util = 0.0
        if duration > 0:
            gcd_util = min(1.0, atk.gcd_占用毫秒 / duration)

        share = {}
        if total_dmg > 0:
            share = {k: v / total_dmg for k, v in sorted(atk.技能伤害.items(), key=lambda x: -x[1])}

        result = 战斗结果(
            时长毫秒=duration,
            事件数=事件数,
            伤害总量=total_dmg,
            日志=[
                f"{s.get('t', 0):.0f}ms {s.get('skill')} dmg={s.get('damage', 0):.1f}"
                for s in self.sample[:50]
            ],
            指标={
                "DPS": dps,
                "HPS": hps,
                "伤害总量": total_dmg,
                "治疗总量": total_heal,
                "TTK": ttk,
                "GCD利用率": gcd_util,
                "事件数": 事件数,
                "时长毫秒": duration,
                "技能伤害占比": share,
                "技能伤害": dict(atk.技能伤害),
                "技能治疗": dict(atk.技能治疗),
                "施法次数": dict(atk.施法次数),
                "攻方构筑": self.攻方构筑,
                "守方构筑": self.守方构筑,
                "守方剩余生命": dfd.实体.生命,
                "期望模式": self.期望模式,
                "路径": "EV" if self.期望模式 else "MC",
                "stub": False,
                "引擎": "技能战斗引擎",
            },
            结算={"sample_steps": len(self.sample)},
        )
        # attach sample on result via 指标 for batch
        result.指标["sample"] = self.sample
        return result

    def _ready_skills(self, actor: _运行体, now: float) -> list[_运行技]:
        if actor.casting or now < actor.busy_until - 1e-9:
            return []
        if now < actor.gcd_ready_at - 1e-9:
            return []
        ready = [sk for sk in actor.技能 if now >= sk.cd_ready_at - 1e-9]
        return ready

    def _snapshot(self, actor: _运行体, target: _运行体, now: float) -> dict:
        return 感知快照(
            now_ms=now,
            self_hp=float(actor.实体.生命),
            self_hp_max=float(actor.实体.生命上限),
            target_hp=float(target.实体.生命),
            target_hp_max=float(target.实体.生命上限),
            gcd_ready_at=actor.gcd_ready_at,
            busy_until=actor.busy_until,
            resources={},
            buffs=list(actor.buffs.keys()),
            distance=1.0,
        )

    def _pick(
        self,
        ready: list[_运行技],
        *,
        snap: dict,
        panel: dict,
    ) -> tuple[_运行技 | None, dict]:
        if not ready:
            return None, {"候选": [], "理由": "无可用技能"}
        return 选技_1ply(ready, snap, panel)

    def _decide(self, aid: str, actors: dict[str, _运行体], now: float) -> None:
        if now > self.上限毫秒:
            return
        actor = actors[aid]
        if not actor.实体.存活:
            return
        target = actors["B" if aid == "A" else "A"]
        ready = self._ready_skills(actor, now)
        snap = self._snapshot(actor, target, now)
        panel = _effective_panel(actor)
        sk, decision = self._pick(ready, snap=snap, panel=panel)
        if sk is None:
            waits = []
            if actor.gcd_ready_at > now:
                waits.append(actor.gcd_ready_at)
            if actor.busy_until > now:
                waits.append(actor.busy_until)
            for s in actor.技能:
                if s.cd_ready_at > now:
                    waits.append(s.cd_ready_at)
            if waits:
                t = min(waits)
                if t <= self.上限毫秒:
                    self.调度器.调度(t, KIND_DECIDE, {"actor": aid})
            return

        # 记录决策 Sample（择技瞬间）
        self.sample.append(
            {
                "t": now,
                "type": "decide",
                "actor": actor.实体.名称,
                "skill": sk.名称,
                "skill_id": sk.编号,
                "score": decision.get("分数"),
                "snapshot": decision.get("快照"),
                "candidates": decision.get("候选"),
                "reason": "1ply_state_value",
            }
        )

        actor.casting = True
        cast_t = max(0.0, sk.吟唱毫秒)
        finish = now + cast_t
        self.调度器.调度(
            finish,
            KIND_CAST_COMPLETE,
            {"actor": aid, "skill": sk.名称, "skill_id": sk.编号},
        )

    def _on_cast_complete(self, payload: dict, actors: dict[str, _运行体], now: float) -> None:
        aid = payload["actor"]
        actor = actors[aid]
        sk = next((s for s in actor.技能 if s.名称 == payload["skill"]), None)
        if sk is None:
            actor.casting = False
            return
        actor.casting = False
        # 资源/CD/GCD
        sk.cd_ready_at = now + max(0.0, sk.冷却毫秒)
        if sk.占用GCD:
            gcd = max(0.0, sk.公共冷却毫秒)
            actor.gcd_ready_at = now + gcd
            actor.gcd_占用毫秒 += gcd
        action = max(0.0, sk.动作毫秒)
        actor.busy_until = max(actor.busy_until, now + action)
        # 命中：即时（吟唱结束即 impact）；多段可按间隔展开，此处同帧多段
        self.调度器.调度(
            now,
            KIND_IMPACT,
            {"actor": aid, "skill": sk.名称, "skill_id": sk.编号},
        )
        # 下一决策
        next_t = max(actor.gcd_ready_at, actor.busy_until, sk.cd_ready_at)
        # 实际上 GCD 到了就能再决策（即使技能 CD 中可选其他）
        next_t = max(actor.gcd_ready_at, actor.busy_until)
        if next_t <= self.上限毫秒:
            self.调度器.调度(next_t, KIND_DECIDE, {"actor": aid})

    def _on_impact(
        self,
        payload: dict,
        actors: dict[str, _运行体],
        now: float,
    ) -> None:
        aid = payload["actor"]
        actor = actors[aid]
        target = actors["B" if aid == "A" else "A"]
        sk = next((s for s in actor.技能 if s.名称 == payload["skill"]), None)
        if sk is None:
            return
        actor.施法次数[sk.名称] = actor.施法次数.get(sk.名称, 0) + 1
        atk_panel = _effective_panel(actor)
        pipe_dmg = "伤害PVP" if self.模式 == "PVP" else "伤害PVE"
        pipe_heal = "治疗PVP" if self.模式 == "PVP" else "治疗PVE"
        forced = bool(self.强制命中 or sk.命中位 == "必中")
        total_hit = 0.0
        total_heal = 0.0

        if sk.伤害段:
            for seg_expr in 切段(sk.伤害段):
                base = float(求值(seg_expr, atk_panel))
                ev = 事件(
                    时间毫秒=now,
                    序号=0,
                    种类=KIND_IMPACT,
                    载荷={
                        "攻方id": actor.实体.id,
                        "守方id": target.实体.id,
                        "基础伤害": base,
                        "伤害类型": sk.数值类型,
                        "管线": pipe_dmg,
                        "强制命中": forced,
                        "命中位": sk.命中位,
                        "技能": sk.名称,
                    },
                )
                hit = self._结算._处理命中(ev, actor.实体, target.实体)
                total_hit += float(hit.get("最终伤害") or hit.get("实际扣血") or 0.0)

        if sk.治疗解析式:
            base_h = float(求值(sk.治疗解析式, atk_panel))
            evh = 事件(
                时间毫秒=now,
                序号=0,
                种类=KIND_IMPACT,
                载荷={
                    "攻方id": actor.实体.id,
                    "守方id": actor.实体.id,
                    "基础伤害": 0.0,
                    "基础治疗": base_h,
                    "伤害类型": sk.数值类型,
                    "管线": pipe_heal,
                    "管线请求": "治疗",
                    "强制命中": True,
                    "技能": sk.名称,
                },
            )
            hout = self._结算._处理命中(evh, actor.实体, actor.实体)
            total_heal += float(hout.get("实际治疗") or 0.0)

        if total_hit > 0:
            actor.伤害总量 += total_hit
            actor.技能伤害[sk.名称] = actor.技能伤害.get(sk.名称, 0.0) + total_hit
        if total_heal > 0:
            actor.治疗总量 += total_heal
            actor.技能治疗[sk.名称] = actor.技能治疗.get(sk.名称, 0.0) + total_heal
        if total_hit > 0 or total_heal > 0:
            self.sample.append(
                {
                    "t": now,
                    "type": "impact",
                    "actor": actor.实体.名称,
                    "skill": sk.名称,
                    "skill_id": sk.编号,
                    "level": sk.等级,
                    "damage": total_hit,
                    "heal": total_heal,
                    "target_hp": target.实体.生命,
                    "管线": pipe_dmg if total_hit else pipe_heal,
                }
            )

        if sk.效果绑定:
            self._apply_buff(actor if aid == "A" else target, sk, now)

    def _apply_buff(self, target: _运行体, sk: _运行技, now: float) -> None:
        elv = getattr(self.world, "效果等级", None)
        if not elv:
            return
        try:
            row = elv.取(sk.效果绑定, sk.效果等级 or sk.等级)
        except Exception:  # noqa: BLE001
            return
        if not row or row.效果时间 is None:
            return
        dur = float(row.效果时间)
        if dur <= 0:
            return
        mods = _parse_mods(getattr(row, "修正表达式", "") or "")
        target.buffs[sk.效果绑定] = {"mods": mods, "expire": now + dur}
        self.调度器.调度(
            now + dur,
            KIND_BUFF_EXPIRE,
            {"actor": target.实体.id if target.实体.id in ("A", "B") else "A", "buff": sk.效果绑定},
        )


SkillCombatEngine = 技能战斗引擎


# ---------------------------------------------------------------------------
# Phase D 适配：多目标/分段路由（不改写既有 1v1 DES 主循环）
# ---------------------------------------------------------------------------
def 施放技能_经路由(引擎, 攻方, 主目标, 技能描述):
    """薄适配：转发到 `内核.技能路由.施放技能`，保持本模块 import 稳定。"""
    from 战斗模拟.内核.技能路由 import 施放技能 as _施放

    return _施放(引擎, 攻方, 主目标, 技能描述)
