# -*- coding: utf-8 -*-
"""一场战斗收成指标。长表给 MC 分位；矩阵写回见 write/matrix。"""
from __future__ import annotations

import math

# 指标名, 层级, 主体, 单位, 口径, 用途
CATALOG = [
    # —— 对局 ——
    ("胜负", "对局", "对局", "数值", "敌方全灭为 1，否则为 0", "平衡"),
    ("战斗时长", "对局", "对局", "秒", "时间轴停表，取最后一条事件", "平衡"),
    ("TTK", "对局", "对局", "秒", "敌方全部死亡时间；未清场则等于战斗时长", "平衡"),
    ("清场效率", "对局", "对局", "每秒", "击杀数除以战斗时长", "平衡"),
    ("死亡数", "对局", "对局", "个数", "生命降到 0 的单位数", "平衡"),
    ("团灭时间", "对局", "对局", "秒", "我方全灭时间；未团灭为空", "平衡"),
    ("阶段切换时刻", "对局", "对局", "秒", "首次进阶段事件时间", "平衡"),
    ("狂暴触发", "对局", "对局", "数值", "任一方进入狂暴为 1", "平衡"),
    # —— 阵营 ——
    ("剩余生命%", "对局", "阵营", "%", "阵营当前生命合计除以生命上限合计", "平衡"),
    ("阵营伤害", "量", "阵营", "数值", "阵营内单位造成伤害之和", "平衡"),
    ("阵营承伤", "量", "阵营", "数值", "阵营内单位实际掉血之和", "平衡"),
    ("阵营治疗", "量", "阵营", "数值", "阵营内单位治疗之和", "平衡"),
    ("阵营过疗%", "防御浪费", "阵营", "%", "阵营过疗除以阵营治疗", "平衡"),
    ("阵营有效DPS", "量", "阵营", "数值", "阵营伤害除以战斗时长", "平衡"),
    ("阵营死亡数", "对局", "阵营", "个数", "该阵营死亡单位数", "平衡"),
    # —— 单位·量 ——
    ("击杀时间", "对局", "单位", "秒", "该单位第一次把目标打到 0 的时间", "平衡"),
    ("存活时间", "对局", "单位", "秒", "死亡时间；没死则等于战斗时长", "平衡"),
    ("活跃时间%", "时间利用", "单位", "%", "存活时间除以战斗时长", "平衡"),
    ("击杀数", "对局", "单位", "个数", "由该单位打到 0 的目标数", "平衡"),
    ("伤害", "量", "单位", "数值", "实际打掉的生命", "平衡"),
    ("承伤", "量", "单位", "数值", "自己实际掉的生命", "平衡"),
    ("治疗", "量", "单位", "数值", "实际加上的生命", "平衡"),
    ("DPS", "量", "单位", "数值", "伤害除以战斗时长", "平衡"),
    ("HPS", "量", "单位", "数值", "治疗除以战斗时长", "平衡"),
    ("DTPS", "量", "单位", "数值", "承伤除以战斗时长", "平衡"),
    ("有效DPS", "量", "单位", "数值", "伤害除以存活时间", "平衡"),
    ("有效HPS", "量", "单位", "数值", "治疗除以存活时间", "平衡"),
    ("有效DTPS", "量", "单位", "数值", "承伤除以存活时间", "平衡"),
    ("伤害份额", "量", "单位", "%", "单位伤害除以本阵营伤害", "价值"),
    ("治疗份额", "量", "单位", "%", "单位治疗除以本阵营治疗", "价值"),
    ("承伤份额", "量", "单位", "%", "单位承伤除以本阵营承伤", "价值"),
    ("普攻伤害", "量", "单位", "数值", "标签或类型含普攻的命中伤害", "价值"),
    ("技能伤害", "量", "单位", "数值", "非普攻、非持续的命中伤害", "价值"),
    ("持续伤害", "量", "单位", "数值", "伤害来源为持续的命中伤害", "价值"),
    ("机制伤害", "量", "单位", "数值", "场景机制打出的伤害", "平衡"),
    ("溅射伤害", "量", "单位", "数值", "主目标以外的溅射实际伤害", "价值"),
    ("直伤承伤", "量", "单位", "数值", "非持续非机制的承伤", "平衡"),
    ("持续承伤", "量", "单位", "数值", "持续来源承伤", "平衡"),
    ("机制承伤", "量", "单位", "数值", "机制来源承伤", "平衡"),
    ("反伤承伤", "量", "单位", "数值", "自己吃到的反伤", "平衡"),
    ("过量击杀", "量", "单位", "数值", "最终伤害高出实际掉血的部分", "平衡"),
    # —— 单位·时间 ——
    ("公共冷却占用", "时间利用", "单位", "秒", "每次出手占用的公共冷却合计", "平衡"),
    ("动作锁占用", "时间利用", "单位", "秒", "吟唱加动作加引导的合计", "平衡"),
    ("吟唱占用", "时间利用", "单位", "秒", "吟唱时长合计", "平衡"),
    ("空转", "时间利用", "单位", "秒", "战斗时长减去动作锁和走位", "平衡"),
    ("走位占用", "时间利用", "单位", "秒", "靠近和回活动范围占用的决策间隔", "平衡"),
    ("时间利用率", "时间利用", "单位", "%", "动作锁除以战斗时长", "平衡"),
    ("GCD利用率", "时间利用", "单位", "%", "公共冷却占用除以存活时间", "平衡"),
    ("施法密度", "时间利用", "单位", "每秒", "出手次数除以存活时间", "平衡"),
    ("首次出手", "时间利用", "单位", "秒", "第一次造成伤害或治疗的时间", "平衡"),
    ("决策延迟累计", "时间利用", "单位", "秒", "反应延迟与失误延后合计", "平衡"),
    ("就绪空转", "时间利用", "单位", "秒", "有技能就绪却未出手的决策间隔合计", "平衡"),
    # —— 单位·资源 ——
    ("资源消耗", "资源", "单位", "数值", "施放时扣掉的资源", "平衡"),
    ("资源回复", "资源", "单位", "数值", "技能回复和打断返还", "平衡"),
    ("结束资源", "资源", "单位", "数值", "停表时各资源池之和", "平衡"),
    ("溢出", "资源", "单位", "数值", "回复超出开场资源的部分", "平衡"),
    ("资源利用率", "资源", "单位", "%", "消耗除以消耗与结束资源之和", "价值"),
    ("资源峰值", "资源", "单位", "数值", "战斗中资源池观察到的最大值", "平衡"),
    ("资源谷值", "资源", "单位", "数值", "战斗中资源池观察到的最小值", "平衡"),
    ("打不起", "资源", "单位", "次数", "资源不够而没出手的决策次数", "平衡"),
    # —— 单位·防御 ——
    ("护盾吸收", "防御浪费", "单位", "数值", "护盾层被扣掉的量", "平衡"),
    ("护盾剩余", "防御浪费", "单位", "数值", "停表时护盾层剩余", "平衡"),
    ("破盾", "防御浪费", "单位", "次数", "护盾从有到无的次数", "平衡"),
    ("过疗", "防御浪费", "单位", "数值", "治疗管线写出的过量治疗", "平衡"),
    ("过疗%", "防御浪费", "单位", "%", "过疗除以治疗", "平衡"),
    ("吸血", "防御浪费", "单位", "数值", "伤害管线写出的吸血量", "平衡"),
    ("反伤", "防御浪费", "单位", "数值", "伤害管线写出的反伤量", "平衡"),
    ("格挡减免", "防御浪费", "单位", "数值", "格挡免伤效果扣掉的伤害", "平衡"),
    ("减伤减免", "防御浪费", "单位", "数值", "免伤/抗性相对基础伤害扣掉的量", "平衡"),
    ("无敌覆盖", "防御浪费", "单位", "秒", "不可选中或无敌状态合计", "平衡"),
    ("承伤压力", "防御浪费", "单位", "%", "承伤除以生命上限", "平衡"),
    ("过量转盾", "防御浪费", "单位", "数值", "过量治疗转成护盾的量", "平衡"),
    # —— 单位·判定 ——
    ("出手次数", "判定", "单位", "次数", "进入伤害或治疗结算的次数", "平衡"),
    ("命中", "判定", "单位", "次数", "没有闪避的出手", "平衡"),
    ("未中", "判定", "单位", "次数", "闪避成功的出手", "平衡"),
    ("闪避", "判定", "单位", "次数", "被自己闪掉的出手，记在守方", "平衡"),
    ("格挡", "判定", "单位", "次数", "格挡减免大于 0 的出手", "平衡"),
    ("暴击", "判定", "单位", "次数", "打上已暴击标记的出手", "平衡"),
    ("命中率", "判定", "单位", "%", "命中次数除以出手次数", "平衡"),
    ("闪避率", "判定", "单位", "%", "闪避次数除以被击次数", "平衡"),
    ("格挡率", "判定", "单位", "%", "格挡次数除以被击次数", "平衡"),
    ("暴击率", "判定", "单位", "%", "暴击次数除以命中次数", "平衡"),
    ("打断次数", "判定", "单位", "次数", "吟唱被控制取消的次数", "平衡"),
    ("被打断损失锁定", "判定", "单位", "秒", "被打断时剩余吟唱/动作估计", "平衡"),
    ("失误次数", "判定", "单位", "次数", "失误率触发的空决策次数", "平衡"),
    # —— 单位·效果/控制 ——
    ("施加", "效果空间", "单位", "次数", "成功挂上的效果次数", "平衡"),
    ("驱散", "效果空间", "单位", "次数", "驱散管线移除的效果次数", "平衡"),
    ("控制覆盖", "效果空间", "单位", "秒", "自己施加的控制时长合计", "平衡"),
    ("硬控覆盖", "效果空间", "单位", "秒", "击飞/眩晕/定身等硬控施加时长", "平衡"),
    ("软控覆盖", "效果空间", "单位", "秒", "减速等软控施加时长", "平衡"),
    ("被控", "效果空间", "单位", "秒", "自己吃到的控制时长合计", "平衡"),
    ("被硬控", "效果空间", "单位", "秒", "自己吃到的硬控时长", "平衡"),
    ("空放", "效果空间", "单位", "次数", "出手被闪避的次数", "平衡"),
    ("踩陷阱", "效果空间", "单位", "次数", "吃到范围效果伤害的次数", "平衡"),
    ("跳伤", "效果空间", "单位", "数值", "持续来源的伤害，按单位合计", "价值"),
    ("平均层数", "效果空间", "单位", "层", "停表时效果实例层数的平均", "平衡"),
    # —— 单位·空间/仇恨 ——
    ("移动距离", "空间", "单位", "米", "靠近、回位、位移走过的路程", "平衡"),
    ("平均距离", "空间", "单位", "米", "每次决策时与当前目标的距离平均", "平衡"),
    ("脱战次数", "空间", "单位", "次数", "距离超过脱战距离的次数", "平衡"),
    ("位移次数", "空间", "单位", "次数", "自身位移技能的次数", "平衡"),
    ("溅射命中", "空间", "单位", "次数", "主目标以外的溅射结算次数", "平衡"),
    ("被位移", "空间", "单位", "次数", "被击飞/击退次数", "平衡"),
    ("撞墙", "空间", "单位", "次数", "位移撞边界次数", "平衡"),
    ("近战槽", "空间", "单位", "数值", "平均距离≤3 为 1", "平衡"),
    ("仇恨", "空间", "单位", "数值", "仇恨表合计", "平衡"),
    ("拉仇恨时间", "空间", "单位", "秒", "首次成为目标最高仇恨的时间", "平衡"),
    ("OT次数", "空间", "单位", "次数", "仇恨第一名易主次数", "平衡"),
    ("最高仇恨比", "空间", "单位", "%", "自身仇恨除以同阵营最高仇恨", "平衡"),
    ("嘲讽覆盖", "空间", "单位", "秒", "嘲讽状态合计", "平衡"),
    ("召唤在场", "空间", "单位", "秒", "名下召唤物存活时长合计", "平衡"),
    ("召唤伤害", "空间", "单位", "数值", "名下召唤物造成伤害", "平衡"),
    ("死亡率", "对局", "单位", "数值", "死亡为 1", "平衡"),
    ("胜率", "对局", "单位", "数值", "本方胜利为 1", "平衡"),
    ("决策收益差", "价值", "单位", "数值", "推演次优与最优收益差累计", "价值"),
    # —— 技能 ——
    ("施放次数", "量", "技能", "次数", "该技能开始施法的次数", "价值"),
    ("技能伤害", "量", "技能", "数值", "该技能各段实际伤害之和", "价值"),
    ("技能治疗", "量", "技能", "数值", "该技能实际治疗之和", "价值"),
    ("单次伤害", "量", "技能", "数值", "技能伤害除以施放次数", "价值"),
    ("每秒收益", "时间利用", "技能", "数值", "技能伤害加治疗，除以锁定时间", "价值"),
    ("技能份额", "量", "技能", "%", "技能伤害除以该单位总伤害", "价值"),
    ("治疗份额", "量", "技能", "%", "技能治疗除以该单位总治疗", "价值"),
    ("锁定时间", "时间利用", "技能", "秒", "吟唱、动作、引导和公共冷却合计", "价值"),
    ("平均锁定", "时间利用", "技能", "秒", "锁定时间除以施放次数", "价值"),
    ("技能打断", "判定", "技能", "次数", "该技能吟唱被取消的次数", "平衡"),
    ("命中段数", "判定", "技能", "次数", "该技能命中的段数", "价值"),
    ("暴击段数", "判定", "技能", "次数", "该技能暴击的段数", "价值"),
    ("未中段数", "判定", "技能", "次数", "该技能被闪避的段数", "价值"),
    ("主目标伤害", "量", "技能", "数值", "打在锁定主目标上的伤害", "价值"),
    ("溅射伤害", "量", "技能", "数值", "溅射到其他目标的伤害", "价值"),
    ("Cast效率", "时间利用", "技能", "%", "施放次数除以理论最大次数", "价值"),
    ("浪费CD", "时间利用", "技能", "秒", "冷却结束后到再次施放的空档合计", "价值"),
    ("单次施放收益", "量", "技能", "数值", "伤害加治疗除以施放次数", "价值"),
    ("单位时间收益", "时间利用", "技能", "数值", "伤害加治疗除以锁定时间", "价值"),
    # —— 效果 ——
    ("效果施加", "效果空间", "效果", "次数", "该效果被挂上的次数", "价值"),
    ("覆盖时长", "效果空间", "效果", "秒", "该效果写入的持续时间合计", "价值"),
    ("效果跳伤", "效果空间", "效果", "数值", "该效果持续结算打出的伤害", "价值"),
    ("效果覆盖率", "效果空间", "效果", "%", "覆盖时长除以战斗时长", "价值"),
    ("效果贡献", "效果空间", "效果", "数值", "该效果跳伤", "价值"),
    ("效果最大层", "效果空间", "效果", "层", "战斗中观察到的最大层数", "平衡"),
    ("效果平均层", "效果空间", "效果", "层", "施加时层数平均", "平衡"),
    ("被驱散次数", "效果空间", "效果", "次数", "该效果被驱散次数", "平衡"),
]


def catalog_map() -> dict[str, tuple]:
    return {row[0]: row for row in CATALOG}


def _num(unit, key) -> float:
    value = unit.get(key) or 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rate(part, whole) -> float:
    return part / whole if whole else 0.0


def 汇总(outcome: dict, run_id: str, task: str, scene: str, match: str, algorithm: str = "掷骰") -> list[dict]:
    units = list(outcome.get("单位") or [])
    seconds = (outcome.get("时长毫秒") or 0) / 1000
    seconds = seconds or 0.001
    foes_down = all(unit["生命值"] <= 0 for unit in units if unit.get("阵营") == "B") or not any(unit.get("阵营") == "B" for unit in units)
    allies_down = all(unit["生命值"] <= 0 for unit in units if unit.get("阵营") == "A") or not any(unit.get("阵营") == "A" for unit in units)
    kills = sum(1 for unit in units if "死亡时间" in unit)
    ttk = max((_num(u, "死亡时间") for u in units if u.get("阵营") == "B" and "死亡时间" in u), default=None)
    wipe = max((_num(u, "死亡时间") for u in units if u.get("阵营") == "A" and "死亡时间" in u), default=None)
    phase_t = outcome.get("阶段切换毫秒")
    enrage = any("狂暴" in (u.get("标记") or ()) for u in units)
    rows = []

    def emit(subject_kind: str, name: str, camp: str, values: dict):
        for metric, value in values.items():
            if value is None:
                continue
            meta = catalog_map().get(metric)
            rows.append({
                "运行ID": run_id,
                "任务名": task,
                "场景名": scene,
                "对阵": match,
                "阵营": camp,
                "主体名": name,
                "主体": subject_kind,
                "算法": algorithm or "掷骰",
                "样本数": 1,
                "指标名": metric,
                "层级": meta[1] if meta else "",
                "单位": meta[3] if meta else "",
                "口径": meta[4] if meta else "",
                "用途": meta[5] if meta else "",
                "均值": value,
                "标准差": 0,
                "CV": 0,
                "P05": value,
                "P50": value,
                "P95": value,
            })

    emit("对局", "对局", "", {
        "胜负": 1 if foes_down else 0,
        "战斗时长": round(seconds, 4),
        "TTK": (ttk / 1000) if ttk is not None and foes_down else (seconds if foes_down else seconds),
        "清场效率": kills / seconds,
        "死亡数": kills,
        "团灭时间": (wipe / 1000) if wipe is not None and allies_down else None,
        "阶段切换时刻": (float(phase_t) / 1000) if phase_t not in (None, "") else None,
        "狂暴触发": 1 if enrage else 0,
    })

    camp_damage, camp_heal, camp_taken, camp_overheal = {}, {}, {}, {}
    for unit in units:
        camp = unit.get("阵营")
        camp_damage[camp] = camp_damage.get(camp, 0) + _num(unit, "伤害")
        camp_heal[camp] = camp_heal.get(camp, 0) + _num(unit, "治疗")
        camp_taken[camp] = camp_taken.get(camp, 0) + _num(unit, "承伤")
        camp_overheal[camp] = camp_overheal.get(camp, 0) + _num(unit, "过疗")

    for camp in ("A", "B"):
        side = [unit for unit in units if unit.get("阵营") == camp]
        if not side:
            continue
        cap = sum(_num(unit, "生命上限") or _num(unit, "开场生命") for unit in side)
        left = sum(max(0.0, unit["生命值"]) for unit in side)
        heal = camp_heal.get(camp, 0)
        emit("阵营", f"阵营{camp}", camp, {
            "剩余生命%": _rate(left, cap),
            "阵营伤害": camp_damage.get(camp, 0),
            "阵营承伤": camp_taken.get(camp, 0),
            "阵营治疗": heal,
            "阵营过疗%": _rate(camp_overheal.get(camp, 0), heal),
            "阵营有效DPS": camp_damage.get(camp, 0) / seconds,
            "阵营死亡数": sum(1 for u in side if "死亡时间" in u),
        })

    for unit in units:
        name = unit.get("名称")
        camp = unit.get("阵营") or ""
        alive = _num(unit, "死亡时间") / 1000 if "死亡时间" in unit else seconds
        alive = alive or 0.001
        lock = _num(unit, "动作锁") / 1000
        move_t = _num(unit, "走位毫秒") / 1000
        gcd = _num(unit, "公共冷却占用") / 1000
        casts = _num(unit, "出手次数")
        hits = _num(unit, "命中")
        spent = _num(unit, "资源消耗")
        left_res = sum(float(v) for v in (unit.get("资源") or {}).values() if isinstance(v, (int, float)))
        stacks = [item.get("层数") for item in unit.get("效果实例") or [] if isinstance(item.get("层数"), (int, float))]
        shield = sum(float(layer.get("剩余") or 0) for layer in unit.get("护盾层") or [])
        owned = [other for other in units if str(other.get("名称") or "").startswith(f"{name}·")]
        threat = sum(float(v) for v in (unit.get("仇恨表") or {}).values() if isinstance(v, (int, float)))
        avg_dist = _rate(_num(unit, "距离和"), _num(unit, "距离次"))
        cap = _num(unit, "生命上限") or _num(unit, "开场生命")
        won = 1 if (camp == "B" and not foes_down) or (camp == "A" and foes_down) else 0
        dmg = _num(unit, "伤害")
        heal = _num(unit, "治疗")
        taken = _num(unit, "承伤")
        peak = unit.get("资源峰值")
        valley = unit.get("资源谷值")
        same_camp_threat = [
            sum(float(v) for v in (u.get("仇恨表") or {}).values() if isinstance(v, (int, float)))
            for u in units if u.get("阵营") == camp
        ]
        top_threat = max(same_camp_threat) if same_camp_threat else 0
        emit("单位", name, camp, {
            "击杀时间": (_num(unit, "击杀时间") / 1000) if "击杀时间" in unit else None,
            "存活时间": alive,
            "活跃时间%": _rate(alive, seconds),
            "击杀数": _num(unit, "击杀数"),
            "伤害": dmg,
            "承伤": taken,
            "治疗": heal,
            "DPS": dmg / seconds,
            "HPS": heal / seconds,
            "DTPS": taken / seconds,
            "有效DPS": dmg / alive,
            "有效HPS": heal / alive,
            "有效DTPS": taken / alive,
            "普攻伤害": _num(unit, "普攻伤害"),
            "技能伤害": _num(unit, "技能伤害"),
            "持续伤害": _num(unit, "持续伤害"),
            "机制伤害": _num(unit, "机制伤害"),
            "溅射伤害": _num(unit, "溅射伤害"),
            "直伤承伤": _num(unit, "直伤承伤"),
            "持续承伤": _num(unit, "持续承伤"),
            "机制承伤": _num(unit, "机制承伤"),
            "反伤承伤": _num(unit, "反伤承伤"),
            "过量击杀": _num(unit, "过量击杀"),
            "伤害份额": _rate(dmg, camp_damage.get(camp, 0)),
            "治疗份额": _rate(heal, camp_heal.get(camp, 0)),
            "承伤份额": _rate(taken, camp_taken.get(camp, 0)),
            "公共冷却占用": gcd,
            "动作锁占用": lock,
            "吟唱占用": _num(unit, "吟唱占用") / 1000,
            "空转": max(0.0, seconds - lock - move_t),
            "走位占用": move_t,
            "时间利用率": _rate(lock, seconds),
            "GCD利用率": _rate(gcd, alive),
            "施法密度": casts / alive,
            "首次出手": (_num(unit, "首次出手") / 1000) if "首次出手" in unit else None,
            "决策延迟累计": _num(unit, "决策延迟累计") / 1000,
            "就绪空转": _num(unit, "就绪空转") / 1000,
            "资源消耗": spent,
            "资源回复": _num(unit, "资源回复"),
            "结束资源": left_res,
            "溢出": _num(unit, "溢出"),
            "资源利用率": _rate(spent, spent + left_res),
            "资源峰值": float(peak) if isinstance(peak, (int, float)) else left_res,
            "资源谷值": float(valley) if isinstance(valley, (int, float)) else left_res,
            "打不起": _num(unit, "打不起"),
            "护盾吸收": _num(unit, "护盾吸收"),
            "护盾剩余": shield,
            "破盾": _num(unit, "破盾"),
            "过疗": _num(unit, "过疗"),
            "过疗%": _rate(_num(unit, "过疗"), heal),
            "吸血": _num(unit, "吸血"),
            "反伤": _num(unit, "反伤"),
            "格挡减免": _num(unit, "格挡减免"),
            "减伤减免": _num(unit, "减伤减免"),
            "无敌覆盖": _num(unit, "无敌覆盖") / 1000,
            "出手次数": casts,
            "命中": hits,
            "未中": _num(unit, "未中"),
            "闪避": _num(unit, "闪避"),
            "格挡": _num(unit, "格挡"),
            "暴击": _num(unit, "暴击"),
            "命中率": _rate(hits, casts),
            "闪避率": _rate(_num(unit, "闪避"), _num(unit, "被击次数") or casts),
            "格挡率": _rate(_num(unit, "格挡"), _num(unit, "被击次数") or casts),
            "暴击率": _rate(_num(unit, "暴击"), hits),
            "打断次数": _num(unit, "打断次数"),
            "被打断损失锁定": _num(unit, "被打断损失锁定") / 1000,
            "失误次数": _num(unit, "失误次数"),
            "施加": _num(unit, "施加"),
            "驱散": _num(unit, "驱散"),
            "控制覆盖": _num(unit, "控制覆盖"),
            "硬控覆盖": _num(unit, "硬控覆盖"),
            "软控覆盖": _num(unit, "软控覆盖"),
            "被控": _num(unit, "被控"),
            "被硬控": _num(unit, "被硬控"),
            "空放": _num(unit, "空放"),
            "踩陷阱": _num(unit, "踩陷阱"),
            "跳伤": _num(unit, "持续伤害"),
            "平均层数": (sum(stacks) / len(stacks)) if stacks else 0,
            "移动距离": _num(unit, "移动距离"),
            "平均距离": avg_dist,
            "脱战次数": _num(unit, "脱战次数"),
            "位移次数": _num(unit, "位移次数"),
            "溅射命中": _num(unit, "溅射命中"),
            "召唤在场": sum(((_num(other, "死亡时间") / 1000) if "死亡时间" in other else seconds) for other in owned),
            "召唤伤害": sum(_num(other, "伤害") for other in owned),
            "仇恨": threat,
            "拉仇恨时间": (_num(unit, "拉仇恨时间") / 1000) if "拉仇恨时间" in unit else None,
            "OT次数": _num(unit, "OT次数"),
            "最高仇恨比": _rate(threat, top_threat),
            "被位移": _num(unit, "被位移"),
            "撞墙": _num(unit, "撞墙"),
            "近战槽": 1 if avg_dist and avg_dist <= 3 else 0,
            "嘲讽覆盖": _num(unit, "嘲讽覆盖"),
            "过量转盾": _num(unit, "过量转盾"),
            "承伤压力": _rate(taken, cap),
            "死亡率": 1 if "死亡时间" in unit else 0,
            "胜率": won,
            "决策收益差": _num(unit, "决策收益差"),
        })
        for skill, box in (unit.get("技能统计") or {}).items():
            times = box.get("次数") or 0
            damage = box.get("伤害") or 0
            heal_s = box.get("治疗") or 0
            locked = (box.get("锁定") or 0) / 1000
            if not times and not damage and not heal_s:
                continue
            cd = box.get("冷却")
            theor = None
            if isinstance(cd, (int, float)) and cd > 0 and times:
                theor = max(times, math.floor(alive * 1000 / cd) + 1)
            emit("技能", f"{name}·{skill}", camp, {
                "施放次数": times,
                "技能伤害": damage,
                "技能治疗": heal_s,
                "单次伤害": damage / times if times else 0,
                "每秒收益": (damage + heal_s) / locked if locked else 0,
                "技能份额": _rate(damage, dmg),
                "治疗份额": _rate(heal_s, heal),
                "锁定时间": locked,
                "平均锁定": locked / times if times else 0,
                "技能打断": box.get("打断") or 0,
                "命中段数": box.get("命中段") or 0,
                "暴击段数": box.get("暴击段") or 0,
                "未中段数": box.get("未中段") or 0,
                "主目标伤害": box.get("主目标伤害") or damage,
                "溅射伤害": box.get("溅射伤害") or 0,
                "Cast效率": _rate(times, theor) if theor else None,
                "浪费CD": (box.get("浪费CD") or 0) / 1000,
                "单次施放收益": (damage + heal_s) / times if times else 0,
                "单位时间收益": (damage + heal_s) / locked if locked else 0,
            })
        for effect, box in (unit.get("效果统计") or {}).items():
            emit("效果", f"{name}·{effect}", camp, {
                "效果施加": box.get("次数") or 0,
                "覆盖时长": (box.get("时长") or 0) / 1000,
                "效果跳伤": box.get("跳伤") or 0,
                "效果覆盖率": _rate((box.get("时长") or 0) / 1000, seconds),
                "效果贡献": box.get("跳伤") or 0,
                "效果最大层": box.get("最大层") or 0,
                "效果平均层": box.get("平均层") or 0,
                "被驱散次数": box.get("驱散") or 0,
            })
    return rows


def 合并样本(rows: list[dict]) -> list[dict]:
    """同一次任务的多次样本收成均值、标准差和分位。"""
    groups: dict[tuple, list] = {}
    meta: dict[tuple, dict] = {}
    for row in rows:
        key = (row.get("任务名"), row.get("场景名"), row.get("对阵"), row.get("阵营"), row.get("主体"), row.get("主体名"), row.get("指标名"))
        try:
            groups.setdefault(key, []).append(float(row.get("均值") or 0))
        except (TypeError, ValueError):
            continue
        meta[key] = row
    out = []
    for key, values in groups.items():
        values = sorted(values)
        count = len(values)
        mean = sum(values) / count
        var = sum((item - mean) ** 2 for item in values) / count
        std = math.sqrt(var)

        def pick(ratio: float) -> float:
            if count == 1:
                return values[0]
            index = min(count - 1, max(0, int(round(ratio * (count - 1)))))
            return values[index]

        base = dict(meta[key])
        base.update({
            "样本数": count,
            "均值": mean,
            "标准差": std,
            "CV": std / mean if mean else 0,
            "P05": pick(0.05),
            "P50": pick(0.50),
            "P95": pick(0.95),
        })
        out.append(base)
    return out
