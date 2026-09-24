"""战斗引擎：事件调度 + 战斗日志 + 流程解释器 + 触发调度（SimC spine）。"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from 战斗模拟.内核.事件 import (
    KIND_IMPACT,
    KIND_TICK,
    事件,
    事件调度器,
    事件种类,
)
from 战斗模拟.内核.战斗日志 import 战斗日志
from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文
from 战斗模拟.内核.触发调度 import 触发调度器
from 战斗模拟.模型.实体 import 实体
from 战斗模拟.世界 import 世界数据


@dataclass
class 战斗结果:
    时长毫秒: float = 0.0
    事件数: int = 0
    指标: dict[str, Any] = field(default_factory=dict)
    日志: list[Any] = field(default_factory=list)
    伤害总量: float = 0.0
    结算: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        log_out: list[Any] = []
        for item in self.日志:
            if hasattr(item, "to_dict"):
                log_out.append(item.to_dict())
            else:
                log_out.append(item)
        return {
            "时长毫秒": self.时长毫秒,
            "事件数": self.事件数,
            "伤害总量": self.伤害总量,
            "指标": self.指标,
            "日志": log_out,
            "结算": self.结算,
        }


def _实体转面板(e: 实体) -> dict[str, Any]:
    # 光环列表用同一引用，便于解释器就地挂载后写回
    auras = getattr(e, "光环列表", None)
    if not isinstance(auras, list):
        auras = []
        try:
            e.光环列表 = auras
        except Exception:
            pass
    d: dict[str, Any] = {
        "id": e.id,
        "名称": e.名称,
        "等级": getattr(e, "等级", 1) or 1,
        "生命": float(e.生命),
        "生命上限": float(e.生命上限),
        "标签": set(e.标签),
        "状态": set(getattr(e, "状态", set()) or set()),
        "标记": set(),
        "护盾层": list(getattr(e, "护盾层", []) or []),
        "光环列表": auras,
        "_实体": e,
    }
    d.update(e.面板 or {})
    # 面板里若也有光环列表，以实体字段为准
    d["光环列表"] = auras
    d["_实体"] = e
    return d


class 战斗引擎:
    """DES 泵事件；命中时经流程解释器跑 伤害PVE/PVP；钩子驱动触发调度。"""

    def __init__(
        self,
        world: 世界数据 | None = None,
        *,
        步长毫秒: float | None = None,
        上限毫秒: float = 60_000.0,
        攻方: 实体 | None = None,
        守方: 实体 | None = None,
        基础伤害: float | None = None,
        伤害类型: str = "物理",
        伤害来源: str = "直接",
        技能仇恨系数: float = 1.0,
        模式: str = "PVE",
        解释器: 流程解释器 | None = None,
        工作簿路径: str | Path | None = None,
        场景种子: int = 0,
        触发: 触发调度器 | None = None,
        加载触发表: bool = True,
        强制命中: bool = False,
        命中位: str | None = None,
        心跳: bool = False,
    ) -> None:
        self.world = world
        self.步长毫秒 = 步长毫秒
        self.上限毫秒 = 上限毫秒
        self.调度器 = 事件调度器()
        self.日志 = 战斗日志()
        self.实体表: dict[str, 实体] = {}
        self.攻方 = 攻方
        self.守方 = 守方
        self.基础伤害 = 基础伤害
        self.伤害类型 = 伤害类型
        self.伤害来源 = 伤害来源
        self.技能仇恨系数 = 技能仇恨系数
        self.模式 = 模式.upper() if 模式 else "PVE"
        self.场景种子 = int(场景种子)
        self.强制命中 = bool(强制命中)
        self.命中位 = 命中位
        self.心跳 = bool(心跳)
        self._rng: random.Random | None = None

        path = 工作簿路径
        if path is None and world is not None:
            path = getattr(world, "工作簿路径", None) or getattr(world, "workbook", None)
        if path is None:
            try:
                from ssot import 框架路径 as _框架路径

                path = _框架路径()
            except FileNotFoundError:
                cand = Path("/workspace/combat-framework/战斗数值框架.xlsx")
                path = cand if cand.is_file() else None
        self._工作簿路径 = Path(path) if path is not None else None

        if 解释器 is not None:
            self.解释器 = 解释器
        else:
            if self._工作簿路径 is not None and self._工作簿路径.is_file():
                try:
                    self.解释器 = 流程解释器(工作簿路径=self._工作簿路径)
                except Exception:
                    self.解释器 = 流程解释器(管线表={})
            else:
                self.解释器 = 流程解释器(管线表={})

        if 触发 is not None:
            self.触发 = 触发
            self.触发.调度器 = self.调度器
            self.触发.日志 = self.日志
        else:
            self.触发 = 触发调度器(调度器=self.调度器, 日志=self.日志)
            if 加载触发表 and self._工作簿路径 is not None and self._工作簿路径.is_file():
                try:
                    self.触发.加载自工作簿(self._工作簿路径)
                except Exception:
                    pass

    def _默认木桩(self) -> tuple[实体, 实体]:
        if self.攻方 is not None and self.守方 is not None:
            return self.攻方, self.守方
        if self._工作簿路径 is None or not self._工作簿路径.is_file():
            raise FileNotFoundError("默认木桩必须从战斗数值框架加载，禁止硬编码生命/面板")
        from ssot.实体工厂 import 从框架构建木桩对

        atk0, dfd0 = 从框架构建木桩对(self._工作簿路径)
        return self.攻方 or atk0, self.守方 or dfd0

    def _管线名(self) -> str:
        return "伤害PVP" if self.模式 == "PVP" else "伤害PVE"

    def _种子rng(self, seed: int) -> random.Random:
        self._rng = random.Random(int(seed))
        self.触发.rng = self._rng
        return self._rng

    def _rng_位点(self) -> int | None:
        if self._rng is None:
            return None
        return None

    def _处理命中(self, ev: 事件, atk: 实体, dfd: 实体) -> dict[str, Any]:
        pipe = str((ev.载荷 or {}).get("管线") or self._管线名())
        # 触发衍生的治疗请求改走治疗管线名
        req = (ev.载荷 or {}).get("管线请求")
        if req == "治疗" or pipe.startswith("治疗"):
            pipe = pipe if pipe.startswith("治疗") else (
                "治疗PVP" if self.模式 == "PVP" else "治疗PVE"
            )
        dtype = str((ev.载荷 or {}).get("伤害类型") or self.伤害类型 or "").strip()
        if not dtype:
            raise ValueError("命中无数值类型，禁止默认物理")
        raw_base = (ev.载荷 or {}).get("基础伤害", self.基础伤害)
        if raw_base is None:
            raise ValueError("命中无基础伤害")
        base = float(raw_base)
        raw_heal = (ev.载荷 or {}).get("基础治疗", 0.0)
        base_heal = 0.0 if raw_heal in (None, "") else float(raw_heal)
        dsrc = str((ev.载荷 or {}).get("伤害来源") or self.伤害来源)
        seg_indep = (ev.载荷 or {}).get("段独立", True)

        atk_panel = _实体转面板(atk)
        dfd_panel = _实体转面板(dfd)
        atk_panel["_实体"] = atk
        dfd_panel["_实体"] = dfd
        ctx = 构建上下文(
            基础伤害=base,
            基础治疗=base_heal,
            伤害类型=dtype,
            伤害来源=dsrc,
            攻方=atk_panel,
            守方=dfd_panel,
            rng=self._rng,
            仇恨系数=self.技能仇恨系数,
            段独立=bool(seg_indep),
            段序号=(ev.载荷 or {}).get("段序号", 0),
            事件种类=getattr(ev, "种类", None) or "IMPACT",
        )
        if (ev.载荷 or {}).get("强制命中", False):
            ctx["标记"].add("必中")
            ctx["命中位"] = "必中"
        elif (ev.载荷 or {}).get("命中位"):
            ctx["命中位"] = str((ev.载荷 or {}).get("命中位"))
        # 段独立=否且共享掷骰：沿用载荷里的命中/暴击标记
        if not seg_indep and (ev.载荷 or {}).get("共享段掷骰"):
            for flag in ((ev.载荷 or {}).get("共享标记") or []):
                ctx["标记"].add(str(flag))

        is_heal = pipe.startswith("治疗") or req == "治疗"

        if pipe not in self.解释器.管线表:
            if self.解释器.管线表:
                raise ValueError(f"战斗流程无管线 {pipe}，禁止平行公式兜底")
            if is_heal:
                from 战斗模拟.管道.治疗 import 解析治疗PVE, 解析治疗PVP
                from 战斗模拟.管道.扣血 import 解析回血PVE

                fn = 解析治疗PVP if pipe.endswith("PVP") else 解析治疗PVE
                heal_base = base_heal if base_heal > 0 else base
                hout = fn(
                    基础治疗=heal_base,
                    healer=atk_panel,
                    target=dfd_panel,
                    rng=self._rng,
                )
                heal_amt = float(hout.get("原始治疗") or hout.get("治疗") or heal_base)
                hb = 解析回血PVE(
                    {
                        "治疗值": heal_amt,
                        "当前生命": dfd.生命,
                        "生命值": dfd.生命上限,
                    }
                )
                applied = float(hb.get("实际治疗") or 0.0)
                dfd.生命 = float(hb.get("当前生命") or dfd.生命)
                return {
                    "最终伤害": 0.0,
                    "实际扣血": 0.0,
                    "实际治疗": applied,
                    "伤害仇恨": 0.0,
                    "命中": True,
                    "暴击": bool(hout.get("暴击")),
                    "格挡": False,
                    "标记": list(hout.get("标记") or []),
                    "管线": pipe,
                }

            from 战斗模拟.管道.伤害 import 解析伤害PVE, 解析伤害PVP
            from 战斗模拟.管道.仇恨 import 解析伤害仇恨PVE

            fn = 解析伤害PVP if pipe.endswith("PVP") else 解析伤害PVE
            fp = getattr(self.world, "公式参数", None) if self.world else None
            hit = fn(
                基础伤害=base,
                attacker=atk_panel,
                defender=dfd_panel,
                伤害类型=dtype,
                公式参数=fp,
                rng=self._rng,
                强制命中=True,
            )
            dmg = float(hit.get("最终伤害") or hit.get("伤害") or 0.0)
            dfd.生命 = max(0.0, float(dfd.生命) - dmg)
            if dfd.生命 <= 0:
                dfd.存活 = False
            threat = 解析伤害仇恨PVE(伤害=dmg, 治疗=0.0, 技能仇恨系数=self.技能仇恨系数)
            hit["伤害仇恨"] = threat["仇恨"]
            hit["实际扣血"] = dmg
            hit["命中"] = True
            hit["暴击"] = bool(hit.get("暴击"))
            hit["标记"] = list(hit.get("标记") or [])
            if hit["暴击"] and "已暴击" not in hit["标记"]:
                hit["标记"].append("已暴击")
            hit["管线"] = pipe
            return hit

        result = self.解释器.执行管线(pipe, ctx)
        self._写回命中结算(atk, dfd, ctx, result)
        marks = set(result.标记 or [])
        hit = {
            "最终伤害": result.最终伤害,
            "实际扣血": result.实际扣血,
            "实际治疗": result.实际治疗,
            "伤害仇恨": result.伤害仇恨,
            "护盾吸收量": float(ctx.get("护盾吸收量") or 0.0),
            "本次破盾数": float(ctx.get("本次破盾数") or 0.0),
            "过量伤害": float(ctx.get("过量伤害") or 0.0),
            "吸血": float(ctx.get("吸血量") or 0.0),
            "反伤": float(ctx.get("反伤量") or 0.0),
            "命中": "已闪避" not in marks,
            "暴击": "已暴击" in marks,
            "格挡": float(ctx.get("格挡减免量") or 0.0) > 0,
            "标记": sorted(marks),
            "步数": result.步数,
            "管线": pipe,
            "已破盾": "已破盾" in marks or float(ctx.get("本次破盾数") or 0.0) > 0,
            "已死亡": "已死亡" in marks or not dfd.存活,
            "攻方已死亡": "攻方已死亡" in marks or not atk.存活,
        }
        return hit

    def _写回命中结算(
        self,
        atk: 实体,
        dfd: 实体,
        ctx: dict[str, Any],
        result: Any,
    ) -> None:
        """将解释器上下文中的生命/护盾/死亡标记写回实体，并派发破碎/死亡事件。"""
        from 战斗模拟.内核.事件 import KIND_DEATH, KIND_SHIELD_BREAK

        def _apply_side(ent: 实体, side: dict[str, Any] | None) -> None:
            if not isinstance(side, dict):
                return
            if "生命" in side or "当前生命" in side:
                ent.生命 = float(side.get("生命") or side.get("当前生命") or 0.0)
            shields = side.get("护盾层")
            if isinstance(shields, list):
                ent.护盾层 = list(shields)
            auras = side.get("光环列表")
            if isinstance(auras, list):
                ent.光环列表 = list(auras)
            if ent.生命 <= 0:
                ent.存活 = False

        _apply_side(atk, ctx.get("攻方"))
        _apply_side(dfd, ctx.get("守方"))

        # 若面板生命未改但结算目标生命/实际扣血已变，兜底
        marks = set(result.标记 or []) if result is not None else set(ctx.get("标记") or [])
        if "已死亡" in marks:
            dfd.存活 = False
            dfd.生命 = 0.0
        if "攻方已死亡" in marks:
            atk.存活 = False
            atk.生命 = 0.0

        now = float(getattr(self.调度器, "现在毫秒", 0.0) or 0.0)
        broken = int(float(ctx.get("本次破盾数") or 0.0))
        if broken > 0 or "已破盾" in marks:
            self.调度器.调度(
                now,
                KIND_SHIELD_BREAK,
                {
                    "目标id": dfd.id,
                    "破盾数": broken,
                    "护盾吸收量": float(ctx.get("护盾吸收量") or 0.0),
                },
            )
            try:
                self.日志.append(
                    now,
                    KIND_SHIELD_BREAK,
                    攻方id=atk.id,
                    守方id=dfd.id,
                    技能或效果="护盾破碎",
                    结果={"破盾数": broken, "护盾吸收量": float(ctx.get("护盾吸收量") or 0.0)},
                )
            except Exception:
                pass
        # 反伤也可能打掉攻方盾：若结算目标曾是攻方且破盾，额外记一条（同 broken 计数）
        if not atk.存活 or "攻方已死亡" in marks:
            self.调度器.调度(
                now,
                KIND_DEATH,
                {"目标id": atk.id, "角色": "攻方"},
            )
            try:
                self.日志.append(
                    now,
                    KIND_DEATH,
                    攻方id=atk.id,
                    守方id=dfd.id,
                    技能或效果="死亡",
                    结果={"目标id": atk.id, "角色": "攻方"},
                )
            except Exception:
                pass
        if not dfd.存活 or "已死亡" in marks:
            self.调度器.调度(
                now,
                KIND_DEATH,
                {"目标id": dfd.id, "角色": "守方"},
            )
            try:
                self.日志.append(
                    now,
                    KIND_DEATH,
                    攻方id=atk.id,
                    守方id=dfd.id,
                    技能或效果="死亡",
                    结果={"目标id": dfd.id, "角色": "守方"},
                )
            except Exception:
                pass

    def _触发上下文(self, hit: dict[str, Any]) -> dict[str, Any]:
        marks = set(hit.get("标记") or [])
        return {
            "标记": marks,
            "暴击": bool(hit.get("暴击") or "已暴击" in marks),
            "命中": bool(hit.get("命中", True)),
            "闪避": "已闪避" in marks or hit.get("命中") is False,
            "最终伤害": hit.get("最终伤害"),
            "管线": hit.get("管线"),
        }

    def _伤害后触发钩子(
        self,
        *,
        atk: 实体,
        dfd: 实体,
        hit: dict[str, Any],
        now: float,
    ) -> None:
        """攻击时始终；成功命中→命中时+受击时；已暴击→暴击时。"""
        ctx = self._触发上下文(hit)
        # 攻击时：挥击即触发（含未命中）
        self.触发.处理钩子(
            "攻击时",
            现在毫秒=now,
            来源id=atk.id,
            目标id=dfd.id,
            上下文=ctx,
        )
        if hit.get("命中", True) and "已闪避" not in set(hit.get("标记") or []):
            self.触发.处理钩子(
                "命中时",
                现在毫秒=now,
                来源id=atk.id,
                目标id=dfd.id,
                上下文=ctx,
            )
            self.触发.处理钩子(
                "受击时",
                现在毫秒=now,
                来源id=dfd.id,  # ICD 归属受击者装备/效果
                目标id=atk.id,
                上下文=ctx,
            )
        if hit.get("暴击") or "已暴击" in set(hit.get("标记") or []):
            self.触发.处理钩子(
                "暴击时",
                现在毫秒=now,
                来源id=atk.id,
                目标id=dfd.id,
                上下文=ctx,
            )

    def 调度光环存续(
        self,
        *,
        目标侧: dict[str, Any] | None = None,
        光环: Any = None,
        来源id: str = "",
        目标id: str = "",
        现在毫秒: float | None = None,
    ) -> dict[str, Any]:
        """挂载后调度 AURA_EXPIRE / AURA_DECAY / DOT_TICK|HOT_TICK。"""
        from 战斗模拟.内核.光环运行时 import 光环实例, 取消光环调度

        now = self.调度器.现在毫秒 if 现在毫秒 is None else float(现在毫秒)
        aura = 光环
        if aura is not None and not isinstance(aura, 光环实例):
            from 战斗模拟.内核.光环运行时 import 光环实例 as _AI
            aura = _AI.from_dict(aura)
        if aura is None:
            return {}
        # 先取消旧调度，避免刷新后重复
        取消光环调度(self.调度器, aura)
        out: dict[str, Any] = {"uid": aura.uid, "效果代号": aura.效果代号}
        payload_base = {
            "来源id": 来源id,
            "目标id": 目标id,
            "效果代号": aura.效果代号,
            "uid": aura.uid,
        }
        dur = float(aura.剩余时长 or 0.0)
        if dur > 0:
            eid = self.调度器.调度(
                now + dur,
                事件种类.光环到期.value,
                dict(payload_base),
            )
            aura.到期事件号 = eid
            out["到期事件号"] = eid
        decay_iv = float(aura.衰减间隔 or 0.0)
        if decay_iv > 0 and int(aura.衰减数量 or 0) > 0:
            eid = self.调度器.调度(
                now + decay_iv,
                事件种类.光环衰减.value,
                {**payload_base, "衰减间隔": decay_iv, "衰减数量": int(aura.衰减数量)},
            )
            aura.衰减事件号 = eid
            out["衰减事件号"] = eid
        tick_iv = float(aura.跳动间隔 or 0.0)
        if tick_iv > 0:
            ntype = str(aura.数值类型 or "")
            if ntype == "治疗":
                kind = 事件种类.持续治疗跳.value
            else:
                kind = 事件种类.持续伤害跳.value
            eid = self.调度器.调度(
                now + tick_iv,
                kind,
                {
                    **payload_base,
                    "跳动间隔": tick_iv,
                    "快照时机": aura.快照时机,
                },
            )
            aura.跳动事件号 = eid
            out["跳动事件号"] = eid
        # 写回侧列表中的同一实例字段
        if isinstance(目标侧, dict):
            from 战斗模拟.内核.光环运行时 import 取光环列表, 同步光环到实体

            for i, a in enumerate(取光环列表(目标侧)):
                if a.uid == aura.uid:
                    目标侧["光环列表"][i] = aura
                    break
            同步光环到实体(目标侧)
        # 实体表写回
        ent = self.实体表.get(目标id)
        if ent is not None and hasattr(ent, "光环列表"):
            lst = list(getattr(ent, "光环列表") or [])
            for i, a in enumerate(lst):
                uid = getattr(a, "uid", None) if not isinstance(a, dict) else a.get("uid")
                if uid == aura.uid:
                    lst[i] = aura
                    break
            ent.光环列表 = lst
        return out

    def 通知光环施加(
        self,
        *,
        来源id: str,
        目标id: str,
        效果代号: str,
        现在毫秒: float | None = None,
        上下文: dict[str, Any] | None = None,
        入队事件: bool = True,
        剩余时长: float | None = None,
        层衰减间隔: float | None = None,
        层衰减数量: int | None = None,
        跳动间隔: float | None = None,
        uid: int | None = None,
    ) -> list[Any]:
        """异常挂载成功后调用：光环施加钩子；并可调度到期/衰减/跳动。"""
        now = self.调度器.现在毫秒 if 现在毫秒 is None else float(现在毫秒)
        ctx = 上下文 or {}
        payload = {
            "来源id": 来源id,
            "目标id": 目标id,
            "效果代号": 效果代号,
        }
        if uid is not None:
            payload["uid"] = uid
        if 入队事件:
            self.调度器.调度(now, 事件种类.光环施加.value, dict(payload))

        # 若上下文带光环实例或可从实体找到，调度存续事件
        aura = ctx.get("_当前光环")
        if aura is None and uid is not None:
            ent = self.实体表.get(目标id)
            if ent is not None:
                for a in getattr(ent, "光环列表", []) or []:
                    au = a.get("uid") if isinstance(a, dict) else getattr(a, "uid", None)
                    if au == uid:
                        aura = a
                        break
        if aura is None and (剩余时长 or 层衰减间隔 or 跳动间隔):
            # 合成临时描述仅用于调度
            from 战斗模拟.内核.光环运行时 import 光环实例

            aura = 光环实例(
                效果代号=效果代号,
                剩余时长=float(剩余时长 or 0.0),
                衰减间隔=float(层衰减间隔 or 0.0),
                衰减数量=int(层衰减数量 or 0),
                跳动间隔=float(跳动间隔 or 0.0),
                uid=int(uid or 0),
            )
        if aura is not None:
            # 允许外部覆盖时长字段
            if 剩余时长 is not None:
                aura.剩余时长 = float(剩余时长)
            if 层衰减间隔 is not None:
                aura.衰减间隔 = float(层衰减间隔)
            if 层衰减数量 is not None:
                aura.衰减数量 = int(层衰减数量)
            if 跳动间隔 is not None:
                aura.跳动间隔 = float(跳动间隔)
            self.调度光环存续(
                光环=aura,
                来源id=来源id,
                目标id=目标id,
                现在毫秒=now,
            )

        return self.触发.处理钩子(
            "光环施加",
            现在毫秒=now,
            来源id=来源id,
            目标id=目标id,
            上下文=ctx,
            额外效果代号=效果代号,
        )

    def 通知光环到期(
        self,
        *,
        来源id: str,
        目标id: str,
        效果代号: str,
        现在毫秒: float | None = None,
        上下文: dict[str, Any] | None = None,
    ) -> list[Any]:
        now = self.调度器.现在毫秒 if 现在毫秒 is None else float(现在毫秒)
        return self.触发.处理钩子(
            "光环到期",
            现在毫秒=now,
            来源id=来源id,
            目标id=目标id,
            上下文=上下文 or {},
            额外效果代号=效果代号,
        )

    def 通知跳动(
        self,
        *,
        来源id: str,
        目标id: str,
        效果代号: str = "",
        现在毫秒: float | None = None,
        上下文: dict[str, Any] | None = None,
    ) -> list[Any]:
        now = self.调度器.现在毫秒 if 现在毫秒 is None else float(现在毫秒)
        return self.触发.处理钩子(
            "每跳动",
            现在毫秒=now,
            来源id=来源id,
            目标id=目标id,
            上下文=上下文 or {},
            额外效果代号=效果代号 or None,
        )

    def 施放技能(
        self,
        攻方: 实体 | None = None,
        主目标: 实体 | str | None = None,
        技能描述: dict | Any = None,
        *,
        skill: dict | Any = None,
    ) -> dict[str, Any]:
        """多目标/分段技能路由入口 → `内核.技能路由.施放技能`。"""
        from 战斗模拟.内核.技能路由 import 施放技能 as _路由施放

        desc = 技能描述 if 技能描述 is not None else skill
        if desc is None:
            raise ValueError("施放技能需要 技能描述")
        atk = 攻方 or self.攻方
        if atk is None:
            raise ValueError("施放技能需要攻方实体")
        tgt = 主目标 if 主目标 is not None else self.守方
        if atk.id not in self.实体表:
            self.实体表[atk.id] = atk
        if isinstance(tgt, 实体) and tgt.id not in self.实体表:
            self.实体表[tgt.id] = tgt
        if self._rng is None:
            self._种子rng(self.场景种子)
        return _路由施放(self, atk, tgt, desc)

    def run_once(self, *, seed: int | None = None) -> 战斗结果:

        seed_v = self.场景种子 if seed is None else int(seed)
        self._种子rng(seed_v)

        atk, dfd = self._默认木桩()
        self.实体表[atk.id] = atk
        self.实体表[dfd.id] = dfd
        self.日志.清空()
        self.调度器.清空()
        self.触发.重置运行时()
        self.触发.调度器 = self.调度器
        self.触发.日志 = self.日志
        self.触发.rng = self._rng

        if self.基础伤害 is None:
            raise ValueError("基础伤害必须来自技能段或面板通道，禁止默认 100")
        self.调度器.调度(
            0.0,
            KIND_IMPACT,
            {
                "攻方id": atk.id,
                "守方id": dfd.id,
                "基础伤害": float(self.基础伤害),
                "伤害类型": self.伤害类型,
                "伤害来源": self.伤害来源,
                "管线": self._管线名(),
                "强制命中": self.强制命中,
                "命中位": self.命中位,
            },
        )
        if self.心跳:
            if self.步长毫秒 is None:
                raise ValueError("心跳开启时步长毫秒必须来自表，禁止默认 100ms")
            self.调度器.调度(0.0, KIND_TICK, {})

        事件数 = 0
        hit: dict[str, Any] = {}
        dmg = 0.0
        time_cap = float(self.上限毫秒)

        while True:
            ev = self.调度器.推进()
            if ev is None:
                break
            事件数 += 1
            kind = ev.种类
            now = self.调度器.现在毫秒

            if kind in (KIND_IMPACT, 事件种类.命中.value, "IMPACT"):
                # 触发衍生的纯手递（治疗/伤害）仍走命中处理
                src_id = str((ev.载荷 or {}).get("攻方id") or atk.id)
                dst_id = str((ev.载荷 or {}).get("守方id") or dfd.id)
                src = self.实体表.get(src_id, atk)
                dst = self.实体表.get(dst_id, dfd)
                hit = self._处理命中(ev, src, dst)
                dmg += float(hit.get("最终伤害") or hit.get("实际扣血") or 0.0)
                self.日志.append(
                    时间毫秒=now,
                    事件种类=事件种类.命中.value,
                    攻方id=src.id,
                    守方id=dst.id,
                    技能或效果=str(
                        (ev.载荷 or {}).get("技能")
                        or (ev.载荷 or {}).get("效果代号")
                        or "木桩打击"
                    ),
                    结果=dict(hit),
                    随机种子位点=self._rng_位点(),
                )
                # 来源触发的衍生命中不再递归打钩子，避免连锁爆炸
                if not (ev.载荷 or {}).get("来源触发"):
                    self._伤害后触发钩子(atk=src, dfd=dst, hit=hit, now=now)

            elif kind in (
                事件种类.施法开始.value,
                事件种类.施法完成.value,
                事件种类.GCD就绪.value,
                "CAST_START",
                "CAST_COMPLETE",
                "GCD_READY",
            ):
                payload = dict(ev.载荷 or {})
                self.日志.append(
                    时间毫秒=now,
                    事件种类=kind,
                    攻方id=str(payload.get("攻方id") or atk.id),
                    守方id=str(payload.get("守方id") or ""),
                    技能或效果=str(payload.get("技能") or ""),
                    结果={"cast_timeline": True, **payload},
                )

            elif kind in (KIND_TICK, 事件种类.心跳.value, "TICK"):
                self.日志.append(
                    时间毫秒=now,
                    事件种类=事件种类.心跳.value,
                    攻方id=atk.id,
                    守方id=dfd.id,
                    技能或效果="",
                    结果={"tick": True},
                )
                if self.步长毫秒 is None:
                    continue
                nxt = now + float(self.步长毫秒)
                if nxt <= time_cap:
                    self.调度器.调度(nxt, KIND_TICK, {})

            elif kind in (事件种类.触发.value, "PROC"):
                payload = dict(ev.载荷 or {})
                self.日志.append(
                    时间毫秒=now,
                    事件种类=事件种类.触发.value,
                    攻方id=str(payload.get("来源") or ""),
                    守方id=str(payload.get("目标") or ""),
                    技能或效果=str(payload.get("效果代号") or ""),
                    结果={"proc": True, **payload},
                )

            elif kind in (事件种类.光环施加.value, "AURA_APPLY"):
                payload = dict(ev.载荷 or {})
                code = str(payload.get("效果代号") or "")
                src = str(payload.get("来源id") or payload.get("来源") or atk.id)
                dst = str(payload.get("目标id") or payload.get("目标") or dfd.id)
                self.日志.append(
                    时间毫秒=now,
                    事件种类=事件种类.光环施加.value,
                    攻方id=src,
                    守方id=dst,
                    技能或效果=code,
                    结果={"aura_apply": True, **payload},
                )
                if not payload.get("来源触发"):
                    self.触发.处理钩子(
                        "光环施加",
                        现在毫秒=now,
                        来源id=src,
                        目标id=dst,
                        上下文={},
                        额外效果代号=code or None,
                    )

            elif kind in (事件种类.光环到期.value, "AURA_EXPIRE"):
                payload = dict(ev.载荷 or {})
                code = str(payload.get("效果代号") or "")
                src = str(payload.get("来源id") or payload.get("来源") or atk.id)
                dst = str(payload.get("目标id") or payload.get("目标") or dfd.id)
                uid = payload.get("uid")
                removed_info: dict[str, Any] = {}
                ent = self.实体表.get(dst)
                if ent is not None:
                    from 战斗模拟.内核.光环运行时 import (
                        取消光环调度,
                        按uid移除,
                        移除同效果,
                        光环实例,
                    )

                    side = _实体转面板(ent)
                    rem = []
                    if uid is not None:
                        inst = 按uid移除(side, int(uid))
                        rem = [inst] if inst else []
                    else:
                        rem = 移除同效果(side, code)
                    for inst in rem:
                        if inst is not None:
                            取消光环调度(self.调度器, inst)
                            removed_info = {
                                "uid": getattr(inst, "uid", None),
                                "到期动作": getattr(inst, "到期动作", ""),
                                "层数": getattr(inst, "层数", 0),
                            }
                    ent.光环列表 = list(side.get("光环列表") or [])
                self.日志.append(
                    时间毫秒=now,
                    事件种类=事件种类.光环到期.value,
                    攻方id=src,
                    守方id=dst,
                    技能或效果=code,
                    结果={"aura_expire": True, **payload, **removed_info},
                )
                self.通知光环到期(
                    来源id=src,
                    目标id=dst,
                    效果代号=code,
                    现在毫秒=now,
                )

            elif kind in (事件种类.光环衰减.value, "AURA_DECAY"):
                payload = dict(ev.载荷 or {})
                code = str(payload.get("效果代号") or "")
                src = str(payload.get("来源id") or payload.get("来源") or atk.id)
                dst = str(payload.get("目标id") or payload.get("目标") or dfd.id)
                uid = payload.get("uid")
                decay_iv = float(payload.get("衰减间隔") or 0.0)
                result_info: dict[str, Any] = {"aura_decay": True, **payload}
                ent = self.实体表.get(dst)
                if ent is not None:
                    from 战斗模拟.内核.光环运行时 import 衰减层数, 取光环列表

                    side = _实体转面板(ent)
                    inst, gone = 衰减层数(
                        side,
                        效果代号=code,
                        uid=int(uid) if uid is not None else None,
                        数量=payload.get("衰减数量"),
                    )
                    ent.光环列表 = list(side.get("光环列表") or [])
                    result_info["已移除"] = gone
                    if inst is not None:
                        result_info["层数"] = inst.层数
                        result_info["uid"] = inst.uid
                    # 仍存活则排下次衰减
                    if not gone and inst is not None and decay_iv > 0:
                        eid = self.调度器.调度(
                            now + decay_iv,
                            事件种类.光环衰减.value,
                            {
                                "来源id": src,
                                "目标id": dst,
                                "效果代号": code,
                                "uid": inst.uid,
                                "衰减间隔": decay_iv,
                                "衰减数量": int(inst.衰减数量 or payload.get("衰减数量") or 1),
                            },
                        )
                        inst.衰减事件号 = eid
                        # 写回
                        for i, a in enumerate(取光环列表(side)):
                            if a.uid == inst.uid:
                                side["光环列表"][i] = inst
                                break
                        ent.光环列表 = list(side.get("光环列表") or [])
                    elif gone and inst is not None:
                        # 层尽 → 当作到期钩子
                        self.触发.处理钩子(
                            "光环到期",
                            现在毫秒=now,
                            来源id=src,
                            目标id=dst,
                            上下文={},
                            额外效果代号=code or None,
                        )
                self.日志.append(
                    时间毫秒=now,
                    事件种类=事件种类.光环衰减.value,
                    攻方id=src,
                    守方id=dst,
                    技能或效果=code,
                    结果=result_info,
                )

            elif kind in (
                事件种类.持续伤害跳.value,
                事件种类.持续治疗跳.value,
                "DOT_TICK",
                "HOT_TICK",
            ):
                payload = dict(ev.载荷 or {})
                code = str(payload.get("效果代号") or "")
                src = str(payload.get("来源id") or payload.get("攻方id") or atk.id)
                dst = str(payload.get("目标id") or payload.get("守方id") or dfd.id)
                uid = payload.get("uid")
                tick_panel: dict[str, Any] = {}
                tick_iv = float(payload.get("跳动间隔") or 0.0)
                ent = self.实体表.get(dst)
                src_ent = self.实体表.get(src)
                if ent is not None:
                    from 战斗模拟.内核.光环运行时 import (
                        取光环列表,
                        跳动属性面板,
                        光环实例,
                    )

                    side = _实体转面板(ent)
                    aura = None
                    for a in 取光环列表(side):
                        if uid is not None and a.uid == int(uid):
                            aura = a
                            break
                        if a.效果代号 == code:
                            aura = a
                    if aura is not None:
                        src_panel = _实体转面板(src_ent) if src_ent is not None else {}
                        tick_panel = 跳动属性面板(aura, src_panel)
                        tick_iv = tick_iv or float(aura.跳动间隔 or 0.0)
                        # 排下一跳（光环仍在）
                        if tick_iv > 0:
                            eid = self.调度器.调度(
                                now + tick_iv,
                                kind,
                                {
                                    **payload,
                                    "uid": aura.uid,
                                    "跳动间隔": tick_iv,
                                    "快照时机": aura.快照时机,
                                },
                            )
                            aura.跳动事件号 = eid
                            ent.光环列表 = list(side.get("光环列表") or [])
                self.日志.append(
                    时间毫秒=now,
                    事件种类=kind,
                    攻方id=src,
                    守方id=dst,
                    技能或效果=code,
                    结果={"tick_effect": True, "快照面板键": list(tick_panel.keys()), **payload},
                )
                self.触发.处理钩子(
                    "每跳动",
                    现在毫秒=now,
                    来源id=src,
                    目标id=dst,
                    上下文={"快照面板": tick_panel},
                    额外效果代号=code or None,
                )
                tick_base = payload.get("基础伤害")
                tick_heal = payload.get("基础治疗")
                try:
                    tick_base_f = 0.0 if tick_base in (None, "") else float(tick_base)
                except (TypeError, ValueError):
                    tick_base_f = 0.0
                try:
                    tick_heal_f = 0.0 if tick_heal in (None, "") else float(tick_heal)
                except (TypeError, ValueError):
                    tick_heal_f = 0.0
                if tick_base_f > 0 or tick_heal_f > 0:
                    is_hot = kind in (事件种类.持续治疗跳.value, "HOT_TICK")
                    mode = "PVP" if self.模式 == "PVP" else "PVE"
                    tick_pipe = (f"治疗{mode}" if is_hot or tick_heal_f > 0 else f"伤害{mode}")
                    tick_dtype = str(
                        payload.get("伤害类型")
                        or (getattr(aura, "数值类型", None) if aura is not None else None)
                        or self.伤害类型
                        or ""
                    ).strip()
                    if not tick_dtype or tick_dtype == "无":
                        tick_dtype = "物理"
                    tick_ev = 事件(
                        时间毫秒=now,
                        序号=int(getattr(ev, "序号", 0) or 0),
                        种类=kind,
                        载荷={
                            **payload,
                            "管线": tick_pipe,
                            "管线请求": "治疗" if tick_pipe.startswith("治疗") else "伤害",
                            "基础伤害": tick_base_f,
                            "基础治疗": tick_heal_f,
                            "伤害来源": "持续",
                            "治疗来源": "持续",
                            "伤害类型": tick_dtype,
                            "强制命中": True,
                        },
                    )
                    src_ent = src_ent if src_ent is not None else atk
                    dst_ent = ent if ent is not None else dfd
                    self._处理命中(tick_ev, src_ent, dst_ent)

            elif kind in (事件种类.驱散.value, "DISPEL"):
                payload = dict(ev.载荷 or {})
                self.日志.append(
                    时间毫秒=now,
                    事件种类=事件种类.驱散.value,
                    攻方id=str(payload.get("来源id") or payload.get("来源") or ""),
                    守方id=str(payload.get("目标id") or payload.get("目标") or ""),
                    技能或效果=str(payload.get("效果代号") or ""),
                    结果={"dispel": True, **payload},
                )

            if now >= time_cap:
                break
            if 事件数 > 10_000:
                break

        metrics = {
            "伤害总量": dmg,
            "仇恨": float(hit.get("伤害仇恨") or 0.0),
            "命中": hit.get("命中"),
            "暴击": hit.get("暴击"),
            "格挡": hit.get("格挡"),
            "吸血": hit.get("吸血"),
            "反伤": hit.get("反伤"),
            "守方剩余生命": dfd.生命,
            "ticks": 事件数,
            "stub": False,
            "管线": hit.get("管线") or self._管线名(),
            "解释器步数": hit.get("步数"),
        }
        metrics.update(self.触发.指标快照())

        result = 战斗结果(
            时长毫秒=self.调度器.现在毫秒,
            事件数=事件数,
            伤害总量=dmg,
            结算=hit,
            日志=self.日志.to_list(),
            指标=metrics,
        )
        return result

    def run(self, *, seed: int | None = None, 时间上限毫秒: float | None = None) -> 战斗结果:
        """泵事件直至队列空或时间盖帽（与 run_once 同骨架，可调上限）。"""
        old_cap = self.上限毫秒
        if 时间上限毫秒 is not None:
            self.上限毫秒 = float(时间上限毫秒)
        try:
            return self.run_once(seed=seed)
        finally:
            self.上限毫秒 = old_cap


CombatEngine = 战斗引擎
CombatResult = 战斗结果
