"""技能路由层：目标选取 → 按目标/段调度 IMPACT / 治疗 / 光环 / 驱散。

架构锁：仅 伤害/治疗/效果事件/驱散 四类 pipe；AoE = 对本模块选出的每个目标各调一次 pipe。
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

from 战斗模拟.内核.事件 import 事件种类
from 战斗模拟.内核.目标选取 import _行取值, _转浮点, _转整数, 选取目标
from 战斗模拟.模型.实体 import 实体

_log = logging.getLogger("战斗模拟.技能路由")


def _是真(v: Any) -> bool:
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("是", "y", "yes", "true", "1", "独立")


def _判技能形态(技能描述: Any) -> dict[str, bool]:
    """根据管线列 / 技能类型 / 显式标志判断走哪些 pipe。"""
    stype = str(_行取值(技能描述, "技能类型", "类型", 默认="") or "").strip()
    dmg_pipe = str(_行取值(技能描述, "伤害管线", 默认="") or "").strip()
    heal_pipe = str(_行取值(技能描述, "治疗管线", 默认="") or "").strip()
    has_base_dmg = _行取值(技能描述, "基础伤害") is not None
    has_base_heal = _行取值(技能描述, "基础治疗") is not None
    aura_list = _行取值(技能描述, "施加效果", "效果列表", "光环效果", 默认=None)
    flag_dispel = _是真(_行取值(技能描述, "驱散", "是否驱散")) or "驱散" in stype
    flag_aura = bool(aura_list) or _是真(_行取值(技能描述, "光环", "是否光环")) or "光环" in stype or "异常" in stype
    flag_heal = bool(heal_pipe) or has_base_heal or "治疗" in stype or _是真(
        _行取值(技能描述, "治疗", "是否治疗")
    )
    flag_dmg = bool(dmg_pipe) or has_base_dmg or "伤害" in stype or "攻击" in stype
    # 默认：有基础伤害或未标明治疗/驱散/光环 → 伤害
    if not any((flag_dmg, flag_heal, flag_aura, flag_dispel)):
        flag_dmg = True
    # 驱散技能通常不打伤害（除非显式给了基础伤害）
    if flag_dispel and not has_base_dmg and not dmg_pipe:
        flag_dmg = False
    return {
        "伤害": flag_dmg,
        "治疗": flag_heal,
        "光环": flag_aura,
        "驱散": flag_dispel,
    }


def _段数(技能描述: Any, *, 治疗: bool = False) -> int:
    if 治疗:
        n = _行取值(技能描述, "治疗段数", "期望段数", "引导段数")
    else:
        n = _行取值(技能描述, "期望段数", "伤害段数", "引导段数", "段数")
    return max(1, _转整数(n, 1))


def _段间隔(技能描述: Any, *, 治疗: bool = False) -> float:
    if 治疗:
        return max(0.0, _转浮点(_行取值(技能描述, "治疗段间隔", "伤害段间隔"), 0.0))
    return max(0.0, _转浮点(_行取值(技能描述, "伤害段间隔", "段间隔"), 0.0))


def _管线名(引擎: Any, 技能描述: Any, *, 治疗: bool = False, 驱散: bool = False) -> str:
    mode = str(getattr(引擎, "模式", "PVE") or "PVE").upper()
    suffix = "PVP" if mode == "PVP" else "PVE"
    if 驱散:
        explicit = str(_行取值(技能描述, "驱散管线", 默认="") or "").strip()
        return explicit or f"驱散{suffix}"
    if 治疗:
        explicit = str(_行取值(技能描述, "治疗管线", 默认="") or "").strip()
        return explicit or f"治疗{suffix}"
    explicit = str(_行取值(技能描述, "伤害管线", 默认="") or "").strip()
    return explicit or f"伤害{suffix}"


def _效果列表(技能描述: Any) -> list[str]:
    raw = _行取值(技能描述, "施加效果", "效果列表", "光环效果", 默认="")
    if raw is None or str(raw).strip() in ("", "无", "—"):
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    parts = []
    for sep in (";", "；", ",", "，", "|"):
        if sep in str(raw):
            parts = [p.strip() for p in str(raw).split(sep) if p.strip()]
            break
    if not parts:
        parts = [str(raw).strip()]
    return parts


def _实体列表(引擎: Any, 攻方: 实体, 主目标: 实体 | None) -> list[实体]:
    table = getattr(引擎, "实体表", None) or {}
    ents = list(table.values()) if table else []
    ids = {e.id for e in ents}
    if 攻方 is not None and 攻方.id not in ids:
        ents.append(攻方)
        ids.add(攻方.id)
    if 主目标 is not None and 主目标.id not in ids:
        ents.append(主目标)
    return ents


def _登记实体(引擎: Any, *ents: 实体 | None) -> None:
    if not hasattr(引擎, "实体表") or 引擎.实体表 is None:
        引擎.实体表 = {}
    for e in ents:
        if e is not None:
            引擎.实体表[e.id] = e


def 施放技能(
    引擎: Any,
    攻方: 实体,
    主目标: 实体 | str | None,
    技能描述: Mapping[str, Any] | Any,
) -> dict[str, Any]:
    """解析目标并调度 CAST / IMPACT / 光环 / 驱散 / GCD 事件。

    返回摘要：目标列表、已调度事件号、段数等。不阻塞等待命中结算——
    由引擎事件泵在 IMPACT 时走 pipe + proc 钩子。
    """
    _登记实体(引擎, 攻方)
    实体表 = getattr(引擎, "实体表", {}) or {}
    if isinstance(主目标, str):
        tgt_ent = 实体表.get(主目标)
    else:
        tgt_ent = 主目标
    if tgt_ent is not None:
        _登记实体(引擎, tgt_ent)

    ents = _实体列表(引擎, 攻方, tgt_ent if isinstance(tgt_ent, 实体) else None)
    rng = getattr(引擎, "_rng", None)
    targets = 选取目标(攻方, 主目标, ents, 技能描述, rng=rng)
    # 确保目标实体已登记（测试可能只传了列表外的桩）
    for tid in targets:
        if tid not in 实体表 and tgt_ent is not None and tgt_ent.id == tid:
            _登记实体(引擎, tgt_ent)

    sch = 引擎.调度器
    now = float(sch.现在毫秒)
    skill_name = str(_行取值(技能描述, "技能名", "名称", "技能", 默认="技能") or "技能")
    skill_id = str(_行取值(技能描述, "技能编号", "编号", 默认="") or "")
    forms = _判技能形态(技能描述)
    segment_indep = _是真(_行取值(技能描述, "段独立", 默认="是"))
    # SimC-likeness：段独立缺省视为独立掷骰
    if _行取值(技能描述, "段独立") is None:
        segment_indep = True

    cast_ms = max(0.0, _转浮点(_行取值(技能描述, "吟唱时长", "吟唱毫秒"), 0.0))
    scheduled: list[int] = []

    # CAST_START → CAST_COMPLETE（时间轴骨架；不硬阻塞）
    scheduled.append(
        sch.调度(
            now,
            事件种类.施法开始.value,
            {
                "攻方id": 攻方.id,
                "守方id": targets[0] if targets else (tgt_ent.id if tgt_ent else ""),
                "技能": skill_name,
                "技能编号": skill_id,
            },
        )
    )
    cast_done_at = now + cast_ms
    scheduled.append(
        sch.调度(
            cast_done_at,
            事件种类.施法完成.value,
            {
                "攻方id": 攻方.id,
                "守方id": targets[0] if targets else "",
                "技能": skill_name,
                "技能编号": skill_id,
                "目标列表": list(targets),
            },
        )
    )

    impact_ids: list[int] = []
    raw_base = _行取值(技能描述, "基础伤害")
    if raw_base is None or str(raw_base).strip() in ("", "—", "-", "无"):
        eng_base = getattr(引擎, "基础伤害", None)
        if eng_base is None:
            raise ValueError("技能无基础伤害且引擎未提供，禁止默认 100")
        base_dmg = float(eng_base)
    else:
        base_dmg = float(raw_base)
    raw_heal = _行取值(技能描述, "基础治疗")
    base_heal = 0.0 if raw_heal is None or str(raw_heal).strip() in ("", "—", "-", "无") else float(raw_heal)
    dtype = str(
        _行取值(技能描述, "数值类型", "伤害类型")
        or getattr(引擎, "伤害类型", "")
        or ""
    ).strip()
    if not dtype:
        raise ValueError("技能无数值类型，禁止默认物理")

    # —— 伤害：每目标 × 每段 → IMPACT ——
    if forms["伤害"] and targets:
        n_seg = _段数(技能描述, 治疗=False)
        interval = _段间隔(技能描述, 治疗=False)
        pipe = _管线名(引擎, 技能描述, 治疗=False)
        for tid in targets:
            for seg_i in range(n_seg):
                t = cast_done_at + interval * seg_i
                payload = {
                    "攻方id": 攻方.id,
                    "守方id": tid,
                    "基础伤害": base_dmg,
                    "伤害类型": dtype,
                    "伤害来源": str(_行取值(技能描述, "伤害来源", 默认="直接") or "直接"),
                    "管线": pipe,
                    "技能": skill_name,
                    "技能编号": skill_id,
                    "段序号": seg_i,
                    "段数": n_seg,
                    "段独立": segment_indep,
                    "强制命中": True,
                }
                if not segment_indep and seg_i > 0:
                    payload["共享段掷骰"] = True
                eid = sch.调度(t, 事件种类.命中.value, payload)
                scheduled.append(eid)
                impact_ids.append(eid)

    # —— 治疗：每目标 × 治疗段 → IMPACT(治疗管线) ——
    if forms["治疗"] and targets:
        n_seg = _段数(技能描述, 治疗=True)
        interval = _段间隔(技能描述, 治疗=True)
        pipe = _管线名(引擎, 技能描述, 治疗=True)
        heal_amt = base_heal if base_heal > 0 else base_dmg
        for tid in targets:
            for seg_i in range(n_seg):
                t = cast_done_at + interval * seg_i
                payload = {
                    "攻方id": 攻方.id,
                    "守方id": tid,
                    "基础伤害": 0.0,
                    "基础治疗": heal_amt,
                    "管线": pipe,
                    "管线请求": "治疗",
                    "技能": skill_name,
                    "技能编号": skill_id,
                    "段序号": seg_i,
                    "段数": n_seg,
                    "段独立": segment_indep,
                    "强制命中": True,
                }
                eid = sch.调度(t, 事件种类.命中.value, payload)
                scheduled.append(eid)
                impact_ids.append(eid)

    # —— 光环 / 效果事件：调度 AURA_APPLY + 通知 ——
    aura_codes = _效果列表(技能描述) if forms["光环"] else []
    aura_events: list[int] = []
    if aura_codes and targets:
        for tid in targets:
            for code in aura_codes:
                eid = sch.调度(
                    cast_done_at,
                    事件种类.光环施加.value,
                    {
                        "来源id": 攻方.id,
                        "目标id": tid,
                        "效果代号": code,
                        "技能": skill_name,
                    },
                )
                scheduled.append(eid)
                aura_events.append(eid)
                # 若引擎支持效果事件 pipe，尝试同步跑一次（失败则仅事件）
                mounted = _尝试异常管线(引擎, 攻方, tid, code, 技能描述)
                # 无效果事件管线或未挂载时仍发钩子（事件已入队）
                if not mounted and hasattr(引擎, "通知光环施加"):
                    try:
                        引擎.通知光环施加(
                            来源id=攻方.id,
                            目标id=tid,
                            效果代号=code,
                            现在毫秒=cast_done_at,
                            入队事件=False,  # 已入队
                        )
                    except Exception as ex:  # noqa: BLE001
                        _log.debug("通知光环施加失败: %s", ex)

    # —— 驱散：对目标跑驱散 pipe（或仅 DISPEL 事件）——
    dispel_events: list[int] = []
    if forms["驱散"]:
        dispel_targets = targets if len(targets) > 1 else (
            targets or ([tgt_ent.id] if tgt_ent is not None else [])
        )
        pipe = _管线名(引擎, 技能描述, 驱散=True)
        for tid in dispel_targets:
            _尝试驱散管线(引擎, 攻方, tid, pipe, 技能描述)
            eid = sch.调度(
                cast_done_at,
                事件种类.驱散.value,
                {
                    "来源id": 攻方.id,
                    "目标id": tid,
                    "管线": pipe,
                    "技能": skill_name,
                },
            )
            scheduled.append(eid)
            dispel_events.append(eid)

    # —— GCD：占用则调度 GCD就绪；时长必须来自技能行 ——
    gcd_id = None
    occupy_raw = _行取值(技能描述, "占用GCD")
    if occupy_raw is None or str(occupy_raw).strip() in ("", "—", "-", "无"):
        raise ValueError("技能无占用GCD，禁止默认占用")
    occupy = _是真(occupy_raw)
    if occupy:
        gcd_raw = _行取值(技能描述, "公共冷却时长", "GCD毫秒", "公共冷却毫秒")
        if gcd_raw is None or str(gcd_raw).strip() in ("", "—", "-", "无"):
            raise ValueError("占用GCD的技能无公共冷却时长，禁止默认 1500ms")
        gcd_ms = float(gcd_raw)
        if gcd_ms < 0:
            raise ValueError(f"公共冷却时长非法: {gcd_ms}")
        gcd_id = sch.调度(
            now + gcd_ms,
            事件种类.GCD就绪.value,
            {"攻方id": 攻方.id, "技能": skill_name},
        )
        scheduled.append(gcd_id)

    summary = {
        "技能": skill_name,
        "技能编号": skill_id,
        "目标": list(targets),
        "目标数": len(targets),
        "形态": forms,
        "段独立": segment_indep,
        "施法完成于": cast_done_at,
        "命中事件": impact_ids,
        "光环事件": aura_events,
        "驱散事件": dispel_events,
        "GCD事件": gcd_id,
        "已调度": scheduled,
    }
    return summary


def _尝试异常管线(
    引擎: Any,
    攻方: 实体,
    目标id: str,
    效果代号: str,
    技能描述: Any,
) -> bool:
    interp = getattr(引擎, "解释器", None)
    if interp is None:
        return False
    mode = str(getattr(引擎, "模式", "PVE") or "PVE").upper()
    suffix = "PVP" if mode == "PVP" else "PVE"
    table = getattr(interp, "管线表", {}) or {}
    pipe = None
    for cand in (f"状态{suffix}", f"效果事件{suffix}", f"异常{suffix}"):
        if cand in table:
            pipe = cand
            break
    if pipe is None:
        return False
    try:
        from 战斗模拟.内核.流程解释器 import 构建上下文
        from 战斗模拟.内核.引擎 import _实体转面板

        dfd = (getattr(引擎, "实体表", {}) or {}).get(目标id)
        if dfd is None:
            return False
        atk_p = _实体转面板(攻方)
        dfd_p = _实体转面板(dfd)
        ctx = 构建上下文(
            攻方=atk_p,
            守方=dfd_p,
            rng=getattr(引擎, "_rng", None),
            效果代号=效果代号,
            _战斗引擎=引擎,
            事件种类=事件种类.光环施加.value,
        )
        # 技能描述可覆盖基础时长/层数等
        if isinstance(技能描述, dict):
            for k in (
                "基础时长", "基础层数", "最大层数", "叠加规则", "刷新规则",
                "快照时机", "快照属性列表", "层衰减间隔", "层衰减数量",
                "跳动间隔", "驱散类型", "驱散类型等级", "可窃取", "标签",
                "互斥组", "效果类型", "数值类型", "到期动作", "附着概率",
            ):
                if k in 技能描述 and 技能描述[k] not in (None, ""):
                    ctx[k] = 技能描述[k]
        result = interp.执行管线(pipe, ctx)
        # 写回光环
        if isinstance(dfd_p.get("光环列表"), list):
            dfd.光环列表 = list(dfd_p["光环列表"])
        if isinstance(atk_p.get("光环列表"), list):
            攻方.光环列表 = list(atk_p["光环列表"])
        # 挂载成功则通知（事件已由路由入队，这里只调度存续+钩子）
        mounted = float(getattr(result, "异常挂载结果", 0) or ctx.get("异常挂载结果") or 0) > 0
        if mounted:
            aura = ctx.get("_当前光环")
            if hasattr(引擎, "通知光环施加"):
                引擎.通知光环施加(
                    来源id=攻方.id,
                    目标id=目标id,
                    效果代号=效果代号,
                    现在毫秒=getattr(getattr(引擎, "调度器", None), "现在毫秒", 0.0),
                    上下文=ctx,
                    入队事件=False,
                    uid=getattr(aura, "uid", None) if aura is not None else None,
                )
        return mounted
    except Exception as ex:  # noqa: BLE001
        _log.debug("效果事件管线跳过: %s", ex)
        return False


def _尝试驱散管线(
    引擎: Any,
    攻方: 实体,
    目标id: str,
    pipe: str,
    技能描述: Any,
) -> None:
    interp = getattr(引擎, "解释器", None)
    if interp is None:
        return
    from 战斗模拟.领域.流程语法 import 规范化管线名

    pipe = 规范化管线名(pipe)
    table = getattr(interp, "管线表", {}) or {}
    if pipe not in table:
        return
    try:
        from 战斗模拟.内核.流程解释器 import 构建上下文
        from 战斗模拟.内核.引擎 import _实体转面板

        dfd = (getattr(引擎, "实体表", {}) or {}).get(目标id)
        if dfd is None:
            return
        atk_p = _实体转面板(攻方)
        dfd_p = _实体转面板(dfd)
        ctx = 构建上下文(
            攻方=atk_p,
            守方=dfd_p,
            rng=getattr(引擎, "_rng", None),
            _战斗引擎=引擎,
            事件种类=事件种类.驱散.value,
        )
        if not ctx.get("驱散强度"):
            ctx["驱散强度"] = 1.0
        if isinstance(技能描述, dict):
            for k in (
                "驱散强度", "驱散类型", "驱散优先级", "可窃取",
            ):
                if k in 技能描述 and 技能描述[k] not in (None, ""):
                    ctx[k] = 技能描述[k]
            # 可窃取技能标记
            if 技能描述.get("可窃取") in (True, "是", 1, "1") or 技能描述.get("可窃取技能"):
                marks = ctx.setdefault("标记", set())
                if isinstance(marks, set):
                    marks.add("可窃取技能")
            if 技能描述.get("强驱") in (True, "是", 1, "1") or "强驱" in str(技能描述.get("标签") or ""):
                marks = ctx.setdefault("标记", set())
                if isinstance(marks, set):
                    marks.add("强驱")
        interp.执行管线(pipe, ctx)
        if isinstance(dfd_p.get("光环列表"), list):
            dfd.光环列表 = list(dfd_p["光环列表"])
        if isinstance(atk_p.get("光环列表"), list):
            攻方.光环列表 = list(atk_p["光环列表"])
    except Exception as ex:  # noqa: BLE001
        _log.debug("驱散管线跳过: %s", ex)


# 英文别名
cast_skill = 施放技能
