"""时间轴。结算走战斗流程，走位用属性总表的速度，缺参数只记入待对齐。"""
from __future__ import annotations

import random
import re

from 战斗模拟.load.curves import _arith
from 战斗模拟.sim.attrs import AttrBag
from 战斗模拟.sim.decide import choose, _ready
from 战斗模拟.sim.engage import apply_heal, apply_hit
from 战斗模拟.sim.expr import 改系数, 求值
from 战斗模拟.sim.flow import FlowHost, _stats
from 战斗模拟.sim.spec import EffectSpec, compile_specs
from 战斗模拟.sim.world import Arena


def _num(value):
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _speed(unit, transfers: dict, gaps: list[str], mode: str | None):
    key = "走路速度" if mode == "走" else "跑步速度"
    attrs = unit["属性"]
    formula = (transfers or {}).get(key)
    if formula and formula != "输入":
        data = attrs.as_dict()

        def resolve(name):
            if name not in data:
                return None
            return data[name]

        value = _arith(str(formula).replace("×", "*"), resolve)
        if isinstance(value, (int, float)):
            return value
    if key in getattr(attrs, "base", {}):
        return attrs.get(key)
    text = f"「{unit['名称']}」没有{key}，属性总表也没有它的转入公式，无法移动"
    if text not in gaps:
        gaps.append(text)
    return None


def _cost_of(unit, spec):
    return unit.get("消耗覆盖", {}).get(spec.name, spec.cost)


def _pay(unit, spec) -> None:
    cost = _cost_of(unit, spec)
    if spec.resource and cost is not None and spec.pay_at != "命中":
        unit["资源"][spec.resource] = unit["资源"].get(spec.resource, 0) - cost
        unit["资源消耗"] = unit.get("资源消耗", 0) + cost


def _refund_pay(unit, spec) -> None:
    cost = _cost_of(unit, spec)
    if spec.resource and cost is not None and spec.pay_at != "命中":
        unit["资源"][spec.resource] = unit["资源"].get(spec.resource, 0) + cost
        unit["资源回复"] = unit.get("资源回复", 0) + cost


def _step_move(unit, arena, other: str, meters: float) -> None:
    name = unit["名称"]
    before = arena.pos.get(name)
    arena.move(name, other, meters)
    after = arena.pos.get(name)
    if before and after:
        _bump(unit, "移动距离", ((after[0] - before[0]) ** 2 + (after[1] - before[1]) ** 2) ** 0.5)


def _bump(unit, key, amount) -> None:
    if not amount:
        return
    unit[key] = unit.get(key, 0) + amount


def _mark_rule(unit, rule, now: float) -> None:
    if not rule:
        return
    name = rule.get("规则名")
    if name is None:
        return
    unit["规则次数"][name] = unit["规则次数"].get(name, 0) + 1
    cd = _num(rule.get("规则冷却"))
    if cd:
        unit.setdefault("规则冷却直到", {})[name] = now + cd


def _tally_hit(attacker, defender, spec, result, now, splash=False) -> None:
    dealt = result.get("伤害") or 0
    reflect = result.get("反伤") or 0
    _bump(attacker, "伤害", dealt)
    _bump(defender, "承伤", dealt)
    _bump(attacker, "吸血", result.get("吸血") or 0)
    _bump(attacker, "反伤", reflect)
    _bump(attacker, "反伤承伤", reflect)
    _bump(defender, "护盾吸收", result.get("护盾吸收") or 0)
    _bump(defender, "格挡减免", result.get("格挡减免") or 0)
    _bump(defender, "减伤减免", result.get("减伤减免") or 0)
    _bump(attacker, "过量击杀", result.get("过量击杀") or 0)
    _bump(attacker, "出手次数", 1)
    _bump(defender, "被击次数", 1)
    if splash:
        _bump(attacker, "溅射命中", 1)
        _bump(attacker, "溅射伤害", dealt)
    origin = result.get("来源") or "直接"
    tags = getattr(spec, "tags", "") or ""
    if origin == "持续":
        _bump(attacker, "持续伤害", dealt)
        _bump(defender, "持续承伤", dealt)
    elif origin == "机制":
        _bump(attacker, "机制伤害", dealt)
        _bump(defender, "机制承伤", dealt)
    elif "普攻" in tags or getattr(spec, "kind", "") == "普攻":
        _bump(attacker, "普攻伤害", dealt)
        _bump(defender, "直伤承伤", dealt)
    else:
        _bump(attacker, "技能伤害", dealt)
        _bump(defender, "直伤承伤", dealt)
    if result.get("闪避"):
        _bump(attacker, "闪避", 1)
        _bump(attacker, "未中", 1)
        _bump(attacker, "空放", 1)
        _bump(defender, "闪避", 1)
    else:
        _bump(attacker, "命中", 1)
    if result.get("暴击"):
        _bump(attacker, "暴击", 1)
    if result.get("格挡"):
        _bump(attacker, "格挡", 1)
        _bump(defender, "格挡", 1)
    if spec is not None and origin != "机制":
        box = attacker.setdefault("技能统计", {}).setdefault(
            spec.name, {"次数": 0, "伤害": 0, "治疗": 0, "锁定": 0, "打断": 0, "段数": 0,
                        "命中段": 0, "暴击段": 0, "未中段": 0, "主目标伤害": 0, "溅射伤害": 0, "浪费CD": 0}
        )
        box["伤害"] += dealt
        box["段数"] += 1
        if result.get("闪避"):
            box["未中段"] = box.get("未中段", 0) + 1
        else:
            box["命中段"] = box.get("命中段", 0) + 1
        if result.get("暴击"):
            box["暴击段"] = box.get("暴击段", 0) + 1
        if splash:
            box["溅射伤害"] = box.get("溅射伤害", 0) + dealt
        else:
            box["主目标伤害"] = box.get("主目标伤害", 0) + dealt
        if origin == "持续":
            effect_box = attacker.setdefault("效果统计", {}).setdefault(spec.name, {"次数": 0, "时长": 0, "跳伤": 0, "最大层": 0, "层和": 0, "驱散": 0})
            effect_box["跳伤"] += dealt
    if "首次出手" not in attacker and dealt:
        attacker["首次出手"] = now
    if defender["生命值"] <= 0 and "死亡时间" not in defender:
        defender["死亡时间"] = now
        attacker["击杀时间"] = attacker.get("击杀时间", now)
        _bump(attacker, "击杀数", 1)
    shield = sum(float(layer.get("剩余") or 0) for layer in defender.get("护盾层") or [])
    if defender.get("_有盾") and shield <= 0:
        _bump(defender, "破盾", 1)
    defender["_有盾"] = shield > 0


def _track_threat(units, now) -> None:
    for target in units:
        scores = []
        for unit in units:
            if unit["阵营"] == target["阵营"] or unit["生命值"] <= 0:
                continue
            hate = (unit.get("仇恨表") or {}).get(target["名称"], 0)
            scores.append((float(hate or 0), unit))
        if not scores:
            continue
        top_hate, top = max(scores, key=lambda item: item[0])
        if top_hate <= 0:
            continue
        prev = target.get("_仇恨榜首")
        if prev and prev != top["名称"]:
            old = next((unit for unit in units if unit["名称"] == prev), None)
            if old is not None:
                _bump(old, "OT次数", 1)
        if "拉仇恨时间" not in top:
            top["拉仇恨时间"] = now
        target["_仇恨榜首"] = top["名称"]


def _resource_extrema(unit) -> None:
    total = sum(float(v) for v in (unit.get("资源") or {}).values() if isinstance(v, (int, float)))
    peak = unit.get("资源峰值")
    valley = unit.get("资源谷值")
    if peak is None or total > peak:
        unit["资源峰值"] = total
    if valley is None or total < valley:
        unit["资源谷值"] = total


def _fill_panel(unit, transfers: dict) -> None:
    """属性总表转入为「输入」的项，面板没写就按未投入的 0。常数和四则式直接算进面板。"""
    attrs = unit["属性"]
    pending = []
    for name, formula in (transfers or {}).items():
        if name in attrs.base:
            continue
        text = str(formula).strip().replace("×", "*")
        if text == "输入":
            attrs.base[name] = 0.0
            continue
        number = _num(text)
        if number is not None and re.fullmatch(r"[+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?", text):
            attrs.base[name] = number
            continue
        pending.append((name, text))
    for _ in range(8):
        if not pending:
            return
        left = []
        for name, formula in pending:
            def resolve(token, bag=attrs):
                if token in bag.base or token in bag.added:
                    return bag.get(token)
                return None

            value = _arith(formula, resolve)
            if value is None:
                left.append((name, formula))
            else:
                attrs.base[name] = float(value)
        if len(left) == len(pending):
            return
        pending = left


def _segments(spec, gaps):
    segments = int(spec.segments or spec.heal_segments or 1)
    chant = spec.chant or 0
    action = spec.action or 0
    if spec.segment_gap is not None:
        return segments, spec.segment_gap, chant + action
    if spec.repeat_gap is not None and segments > 1:
        return segments, spec.repeat_gap, chant + action
    if spec.channel and spec.channel_ticks:
        return int(spec.channel_ticks), spec.channel / spec.channel_ticks, chant + action
    if segments > 1 and action:
        piece = action / segments
        return segments, piece, chant + piece
    if segments > 1:
        text = f"技能「{spec.name}」段数是 {segments}，没有段间隔、连发间隔、引导或动作时长，各段同时结算"
        if text not in gaps:
            gaps.append(text)
    return segments, 0.0, chant + action


def _cancel_cast(unit, events) -> None:
    casting = unit.get("施法")
    if not casting:
        return
    spec = casting[0]
    unit["施法"] = None
    unit["吟唱直到"] = 0
    _refund_pay(unit, spec)
    _bump(unit, "打断次数", 1)
    box = unit.setdefault("技能统计", {}).setdefault(spec.name, {"次数": 0, "伤害": 0, "治疗": 0, "锁定": 0, "打断": 0, "段数": 0})
    box["打断"] += 1
    events[:] = [
        item for item in events
        if not (len(item) >= 4 and item[1] == "命中" and item[2] is unit and item[3] is spec)
    ]


def _mastery_ok(node, unit, spec, target, rng, gaps) -> bool:
    text = str(node.get("条件1表达式") or "").strip()
    if not text:
        return True
    aimed = str(node.get("目标技能") or "")
    names = [part.strip() for part in aimed.replace(";", "；").split("；") if part.strip()]
    if names and spec.name not in names:
        return False
    ok = True
    matched = False
    found = re.search(r"已有\s*(\d+)\s*层\s*(\S+?)的", text)
    if found:
        matched = True
        need = int(found.group(1))
        effect_name = found.group(2)
        stacks = 0
        for item in ((target or unit).get("效果实例") or []):
            if item.get("效果名") == effect_name:
                stacks = max(stacks, item.get("层数") or 1)
        ok = stacks >= need
    found = re.search(r"至少\s*(\d+)\s*个", text)
    if found:
        matched = True
        ok = ok and (unit.get("最近命中数") or 1) >= int(found.group(1))
    found = re.search(r"只命中\s*(\d+)\s*个", text)
    if found:
        matched = True
        ok = ok and (unit.get("最近命中数") or 1) == int(found.group(1))
    found = re.search(r"生命低于\s*(\d+)\s*%", text)
    if found:
        matched = True
        cap = unit.get("生命上限") or 0
        ratio = unit["生命值"] / cap * 100 if cap else 100
        ok = ok and ratio < int(found.group(1))
    found = re.search(r"(\d+)\s*%\s*判定", text)
    if found:
        matched = True
        ok = ok and rng.random() * 100 < int(found.group(1))
    if "耗尽" in text:
        matched = True
        ok = ok and not (target or unit).get("护盾层")
    if not matched:
        line = f"精通「{node.get('节点名')}」的条件没能拆成层数、人数、生命或判定，这次不生效"
        if line not in gaps:
            gaps.append(line)
        return False
    return ok


def _rewrite(unit, spec, target, moment, rng, gaps):
    formula = spec.formula
    nodes = unit.get("命中精通") if moment == "命中" else unit.get("施放精通")
    changed = False
    for node in nodes or []:
        field = str(node.get("目标字段") or "")
        aimed = str(node.get("目标技能") or "")
        names = [part.strip() for part in aimed.replace(";", "；").split("；") if part.strip()]
        if names and spec.name not in names:
            continue
        if not _mastery_ok(node, unit, spec, target, rng, gaps):
            continue
        amount = _num(node.get("数值"))
        if amount is None:
            continue
        if field == "数值解析式" and formula:
            formula = 改系数(str(formula), str(node.get("运算") or ""), amount)
            changed = True
        elif field == "主消耗量" and str(node.get("运算") or "") in ("设", "覆盖"):
            unit.setdefault("消耗覆盖", {})[spec.name] = amount
    return formula if changed else None


def _apply_effect(host, source, target, effect: EffectSpec, now, events, gaps):
    if effect.mark and "免疫" in str(effect.mark):
        target.setdefault("标记", set()).add(effect.mark)
    if effect.control and "免疫常规控制" in target.get("标记", ()):
        return
    current = 0
    for item in target.get("效果实例") or []:
        if item.get("效果名") == effect.name and isinstance(item.get("层数"), (int, float)):
            current = item["层数"]
    host.bind(source, target, effect, {
        "效果代号": effect.name,
        "效果类型": effect.kind or "",
        "效果行": effect.row,
        "叠加规则": effect.stack_rule or "",
        "最大层数": effect.max_stacks if effect.max_stacks is not None else 1,
        "当前层数": current,
        "基础层数": 1,
        "基础时长": effect.duration or 0,
        "剩余时长": effect.duration or 0,
        "刷新规则": effect.refresh or "",
        "互斥组": effect.mutex or "",
        "攻方": _stats(source),
        "守方": _stats(target),
    })
    host.run("状态")
    _bump(source, "施加", 1)
    box = source.setdefault("效果统计", {}).setdefault(effect.name, {"次数": 0, "时长": 0, "跳伤": 0, "最大层": 0, "层和": 0, "驱散": 0})
    box["次数"] += 1
    box["时长"] += effect.duration or 0
    stacks_now = 1
    for item in target.get("效果实例") or []:
        if item.get("效果名") == effect.name and isinstance(item.get("层数"), (int, float)):
            stacks_now = float(item["层数"])
    box["层和"] = box.get("层和", 0) + stacks_now
    box["平均层"] = box["层和"] / max(1, box["次数"])
    box["最大层"] = max(box.get("最大层") or 0, stacks_now)
    if effect.control or effect.control_act:
        seconds = (effect.duration or 0) / 1000
        _bump(source, "控制覆盖", seconds)
        _bump(target, "被控", seconds)
        hard = {"击飞", "眩晕", "定身", "冰冻", "石化", "沉默", "硬直"}
        label = str(effect.control or effect.control_act or "")
        if label in hard:
            _bump(source, "硬控覆盖", seconds)
            _bump(target, "被硬控", seconds)
        else:
            _bump(source, "软控覆盖", seconds)
    for stat, op, value in effect.mods:
        if stat and op and value is not None:
            target["属性"].apply(stat, op, value)
    if effect.duration:
        events.append((now + effect.duration, "效果结束", target, effect.mods))
    if effect.shield not in (None, ""):
        amount = 求值(str(effect.shield).replace("生命值", "攻方(生命值)"), _stats(source), _stats(target))
        host.bind(source, target, effect, {"护盾值": amount, "暴击位": "不可暴击", "攻方": _stats(source), "守方": _stats(target)})
        host.run("护盾")
        given = host.var.get("实际护盾")
        if isinstance(given, (int, float)) and given > 0:
            target.setdefault("护盾层", []).append({"类型": effect.shield_type or "全部", "剩余": float(given)})
    if effect.control_act:
        target.setdefault("状态", set()).add(effect.control_act)
        if effect.duration:
            events.append((now + effect.duration, "控制结束", target, effect.control_act))
    if effect.control == "沉默":
        target.setdefault("状态", set()).add("禁止法术")
    if effect.unselectable == "是":
        target.setdefault("标记", set()).add("不可选中")
        target.setdefault("状态", set()).add("不可选中")
        _bump(target, "无敌覆盖", effect.duration or 0)
        if effect.duration:
            events.append((now + effect.duration, "控制结束", target, "不可选中"))
    if (effect.control or effect.control_act) and target.get("施法"):
        casting = target["施法"][0]
        remain = max(0.0, (target.get("吟唱直到") or now) - now)
        if now < (target.get("吟唱直到") or 0) or casting.interruptible == "是":
            _bump(target, "打断次数", 1)
            _bump(target, "被打断损失锁定", remain)
            box = target.setdefault("技能统计", {}).setdefault(casting.name, {"次数": 0, "伤害": 0, "治疗": 0, "锁定": 0, "打断": 0, "段数": 0})
            box["打断"] = box.get("打断", 0) + 1
            _cancel_cast(target, events)
    if effect.tick and effect.formula:
        jumps = 1
        if effect.duration:
            jumps = max(1, int(effect.duration / effect.tick))
        for index in range(jumps):
            events.append((now + effect.tick * (index + (0 if effect.tick_now == "是" else 1)), "跳动", source, effect, target))
    if effect.radius and effect.shape:
        events.append((now, "范围", source, effect, target, now + (effect.duration or 0)))
    if effect.rewrite_field and effect.rewrite_tag:
        for spec in source["技能规格"].values():
            if effect.rewrite_tag in (spec.tags or ""):
                current = getattr(spec, effect.rewrite_field, None)
                if effect.rewrite_op == "乘" and isinstance(current, (int, float)) and effect.rewrite_value is not None:
                    setattr(spec, effect.rewrite_field, current * effect.rewrite_value)


def _effects(spec, moment, catalog):
    found = []
    for item in spec.effects:
        if (item.get("时机") or "命中") != moment:
            continue
        effect = catalog.get(item["效果"])
        if effect is None:
            continue
        found.append((effect, item.get("延迟") or 0, item.get("目标")))
    return found


def _effect_target(source, primary, hint):
    text = str(hint or "")
    if text in ("自身", "自己", "施法者"):
        return source
    return primary


def _schedule_effects(host, source, primary, items, now, events, gaps):
    for effect, delay, hint in items:
        target = _effect_target(source, primary, hint)
        wait = float(delay or 0)
        if wait > 0:
            events.append((now + wait, "施加效果", source, effect, target))
        else:
            _apply_effect(host, source, target, effect, now, events, gaps)


def _splash_targets(spec, primary, arena, units):
    if not spec.splash or primary is None or primary["名称"] not in arena.pos:
        return []
    found = arena.in_splash(primary["名称"], spec.splash, primary["阵营"], units)
    cap = spec.target_cap
    extra = [unit for unit in found if unit is not primary]
    if cap is None:
        return extra
    return extra[: max(0, int(cap) - 1)]


def _attacker_expr(formula, bag: dict) -> str:
    text = str(formula)
    if "攻方(" in text or "守方(" in text:
        return text
    for name in sorted(bag, key=len, reverse=True):
        if name and name in text:
            text = text.replace(name, f"攻方({name})")
    return text


def _pulse_mechanic(row, now, host, units, arena, contract, gaps, events, limit_ms):
    formula = row.get("数值解析式")
    gap = _num(row.get("间隔"))
    end = _num(row.get("结束"))
    if gap and (end is None or now + gap * 1000 <= end * 1000) and now + gap * 1000 <= limit_ms:
        events.append((now + gap * 1000, "机制", None, row))
    if not formula:
        return
    radius = _num(row.get("半径"))
    camp = str(row.get("目标阵营") or "")
    source = next((unit for unit in units if unit["生命值"] > 0 and unit["阵营"] == "B"), None)
    if source is None:
        source = next((unit for unit in units if unit["生命值"] > 0), None)
    if source is None:
        return
    victims = []
    for unit in units:
        if unit["生命值"] <= 0 or unit["名称"] not in arena.pos:
            continue
        if camp == "敌方" and unit["阵营"] == source["阵营"]:
            continue
        if camp == "友方" and unit["阵营"] != source["阵营"]:
            continue
        if radius is not None:
            x, y = arena.pos[unit["名称"]]
            if (x * x + y * y) ** 0.5 > radius:
                continue
        victims.append(unit)
    from 战斗模拟.sim.spec import SkillSpec
    spec = SkillSpec({
        "技能名": row.get("机制名"),
        "数值解析式": _attacker_expr(formula, source["属性"].as_dict()),
        "数值类型": row.get("数值类型") or "魔法",
        "元素": row.get("元素"),
        "伤害段数": 1,
        "命中规则": "必中",
        "暴击规则": "不可暴击",
        "参与元素克制": "否",
        "参与体型克制": "否",
        "计入吸血": "否",
        "计入反伤": "否",
    }, gaps)
    for victim in victims:
        if victim is source:
            continue
        result = apply_hit(host, source, victim, spec, contract.get("matrices") or {}, gaps, "机制")
        _tally_hit(source, victim, spec, result, now)


def _summon(unit, spec, now, arena, units, events):
    if not spec.summon:
        return
    count = max(1, int(spec.summon_count or 1))
    scale = spec.summon_scale if spec.summon_scale is not None else 1.0
    named = [row for row in unit.get("技能") or [] if str(row.get("技能名")) == str(spec.summon)]
    attacks = named or [
        row for row in unit.get("技能") or []
        if "普攻" in str(row.get("技能类型") or "") or "普攻" in str(row.get("技能标签") or "")
    ]
    for index in range(count):
        name = spec.summon if count == 1 else f"{spec.summon}{index + 1}"
        name = f"{unit['名称']}·{name}"
        attrs = {}
        for key, value in unit["属性"].as_dict().items():
            if key in ("等级",):
                attrs[key] = value
            elif isinstance(value, (int, float)):
                attrs[key] = value * scale
        life = (unit.get("生命上限") or unit["生命值"]) * scale
        child = {
            "名称": name,
            "阵营": unit["阵营"],
            "种类": "召唤",
            "等级": unit.get("等级"),
            "生命值": life,
            "生命上限": life,
            "属性": AttrBag(attrs),
            "资源": {},
            "冷却": {},
            "公共冷却直到": 0.0,
            "伤害": 0.0,
            "治疗": 0.0,
            "护盾层": [],
            "治疗吸收层": [],
            "效果实例": [],
            "标记": set(),
            "状态": set(),
            "仇恨表": {},
            "规则次数": {},
            "阶段": unit.get("阶段") or "P1",
            "施法": None,
            "开场生命": life,
            "开场资源": {},
            "技能": attacks,
            "技能规格": {
                spec_name: item
                for spec_name, item in unit["技能规格"].items()
                if any(row.get("技能名") == spec_name for row in attacks)
            },
            "行为": "",
            "武器": unit.get("武器"),
            "防御元素": unit.get("防御元素"),
            "体型": unit.get("体型"),
            "种族": unit.get("种族"),
            "命中精通": [],
            "施放精通": [],
            "黑板": {},
        }
        units.append(child)
        origin = arena.pos.get(unit["名称"], (0, 0))
        arena.pos[name] = origin
        arena.facing[name] = arena.facing.get(unit["名称"], 0)
        events.append((now, "决策", child))
        if spec.summon_time:
            events.append((now + spec.summon_time, "召唤结束", child))


def run_fight(contract, allies, enemies, limit_ms, step_ms, scene=None, task=None) -> dict:
    gaps = contract.setdefault("待对齐", [])
    if "skill_specs" not in contract:
        compile_specs(contract)
    params = contract.get("params") or {}
    task = task or {}
    seed = task.get("种子")
    if seed in (None, ""):
        gaps.append("批跑任务没有种子，这次随机序列不可复现")
        rng = random.Random()
    else:
        rng = random.Random(int(float(seed)))
    host = FlowHost(contract["curves"], contract["pipes"], gaps, rng)
    arena = Arena(scene, params, gaps)
    delay = _num(task.get("反应延迟"))
    if delay is None:
        delay = _num(params.get("反应延迟默认"))
    if delay is None:
        gaps.append("任务和模拟参数都没有反应延迟")
        delay = 0
    mode = str(task.get("决策模式") or "")
    units = []
    for src in allies + enemies:
        unit = dict(src)
        unit["属性"] = AttrBag(dict(src.get("属性") or {}))
        _fill_panel(unit, contract.get("transfers") or {})
        unit["资源"] = dict(src.get("资源") or {})
        unit["冷却"] = {}
        unit["公共冷却直到"] = 0.0
        unit["伤害"] = 0.0
        unit["治疗"] = 0.0
        unit["护盾层"] = []
        unit["治疗吸收层"] = []
        unit["效果实例"] = []
        unit["标记"] = set()
        unit["状态"] = set()
        unit["仇恨表"] = {}
        unit["规则次数"] = {}
        unit["阶段"] = "P1"
        unit["施法"] = None
        unit["开场生命"] = unit["生命值"]
        unit["开场资源"] = dict(unit["资源"])
        specs = {}
        for row in src.get("技能") or []:
            name = str(row.get("技能名"))
            spec = contract["skill_specs"].get(name)
            if spec:
                specs[name] = spec
        unit["技能规格"] = specs
        unit["黑板"] = dict(src.get("黑板") or {})
        unit["_params"] = params
        if str(unit.get("行为") or "") == "巴风特":
            unit["黑板"].setdefault("BattleState", 1)
            unit["黑板"].setdefault("BodyPart", "Head")
        units.append(unit)
    arena.place(units, contract.get("slots"), str((scene or {}).get("场景名") or ""))
    strategies = {str(s.get("策略名")): s for s in contract.get("strategies") or []}
    if delay:
        for u in units:
            _bump(u, "决策延迟累计", delay)
    events = [(delay, "决策", u) for u in units]
    scene_name = str((scene or {}).get("场景名") or "")
    for row in contract.get("mechanics") or []:
        if str(row.get("场景名") or "") != scene_name or str(row.get("启用") or "是") == "否":
            continue
        trigger = str(row.get("触发类型") or "")
        if trigger == "开战":
            events.append((0, "机制", None, row))
        elif trigger == "时间":
            events.append((((_num(row.get("首次")) or 0) * 1000), "机制", None, row))
    log = []
    now = 0.0
    guard = 0
    while events and guard < 250000:
        guard += 1
        events.sort(key=lambda item: (item[0], 0 if item[1] == "命中" else 1))
        event = events.pop(0)
        now = event[0]
        if now > limit_ms:
            break
        kind = event[1]
        if kind == "机制":
            _pulse_mechanic(event[3], now, host, units, arena, contract, gaps, events, limit_ms)
            continue
        unit = event[2]
        if kind == "效果结束":
            for stat, op, value in event[3]:
                if stat and op and value is not None:
                    unit["属性"].revert(stat, op, value)
            continue
        if kind == "控制结束":
            unit.get("状态", set()).discard(event[3])
            unit.get("标记", set()).discard(event[3])
            continue
        if kind == "施加效果":
            source, effect, victim = event[2], event[3], event[4]
            if victim and victim["生命值"] > 0:
                _apply_effect(host, source, victim, effect, now, events, gaps)
            continue
        if kind == "跳动":
            effect = event[3]
            victim = event[4]
            if victim["生命值"] > 0 and effect.formula:
                fake = contract["skill_specs"].get(effect.name)
                if fake is None:
                    from 战斗模拟.sim.spec import SkillSpec
                    fake = SkillSpec({
                        "技能名": effect.name,
                        "数值解析式": effect.formula,
                        "数值类型": effect.value_type,
                        "元素来源": effect.element_from or "强制",
                        "元素": effect.element,
                        "伤害段数": 1,
                        "命中规则": "必中",
                        "暴击规则": "不可暴击",
                        "伤害仇恨系数": 1,
                        "计入吸血": "否",
                        "计入反伤": "否",
                    }, gaps)
                result = apply_hit(host, unit, victim, fake, contract.get("matrices") or {}, gaps, "持续")
                _tally_hit(unit, victim, fake, result, now)
            continue
        if unit["生命值"] <= 0:
            continue
        if not any(u["生命值"] > 0 and u["阵营"] == "A" for u in units):
            break
        if enemies and not any(u["生命值"] > 0 and u["阵营"] == "B" for u in units):
            break
        if kind == "位移":
            target, meters = event[3], event[4]
            if target["生命值"] > 0 and unit["名称"] in arena.pos and target["名称"] in arena.pos:
                _step_move(unit, arena, target["名称"], meters)
            continue
        if kind == "召唤结束":
            unit["生命值"] = 0
            continue
        if kind == "范围":
            effect = event[3]
            end = event[5] if len(event) > 5 else now
            camp = unit["阵营"] if effect.zone_camp == "友方" else ("A" if unit["阵营"] == "B" else "B")
            if effect.formula and effect.radius and unit["名称"] in arena.pos:
                for victim in arena.in_splash(unit["名称"], effect.radius, camp, units):
                    fake = contract["skill_specs"].get(effect.name)
                    if fake is None:
                        from 战斗模拟.sim.spec import SkillSpec
                        fake = SkillSpec({
                            "技能名": effect.name,
                            "数值解析式": effect.formula,
                            "数值类型": effect.value_type,
                            "元素来源": effect.element_from or "强制",
                            "元素": effect.element,
                            "伤害段数": 1,
                            "命中规则": "必中",
                            "暴击规则": "不可暴击",
                            "伤害仇恨系数": 1,
                            "计入吸血": "否",
                            "计入反伤": "否",
                        }, gaps)
                    result = apply_hit(host, unit, victim, fake, contract.get("matrices") or {}, gaps, "持续")
                    _tally_hit(unit, victim, fake, result, now)
                    _bump(victim, "踩陷阱", 1)
            if effect.tick and now + effect.tick <= end:
                events.append((now + effect.tick, "范围", unit, effect, event[4], end))
            continue
        if kind == "命中":
            spec = event[3]
            target = event[4]
            if unit.get("施法") and unit["施法"][0] is spec and target["生命值"] > 0:
                override = _rewrite(unit, spec, target, "命中", rng, gaps)
                saved = spec.formula
                if override:
                    spec.formula = override
                try:
                    victims = [target] + _splash_targets(spec, target, arena, units)
                    unit["最近命中数"] = len(victims)
                    unit["最近技能"] = spec.name
                    for victim in victims:
                        if victim["生命值"] <= 0:
                            continue
                        if spec.formula:
                            result = apply_hit(host, unit, victim, spec, contract.get("matrices") or {}, gaps)
                            _tally_hit(unit, victim, spec, result, now, splash=victim is not target)
                            log.append({"时间": now, "施法者": unit["名称"], "动作": spec.name, "目标": victim["名称"], "伤害": result["伤害"], "治疗": 0})
                            if result["伤害"] > 0 and victim.get("施法"):
                                casting = victim["施法"][0]
                                if casting.hurt_interrupt == "是":
                                    _cancel_cast(victim, events)
                        if spec.heal_formula and victim is target:
                            healed = apply_heal(host, unit, victim, spec, gaps)
                            unit["治疗"] = unit.get("治疗", 0) + healed
                            over = host.var.get("过量治疗")
                            if isinstance(over, (int, float)):
                                _bump(unit, "过疗", over)
                            box = unit.setdefault("技能统计", {}).setdefault(spec.name, {"次数": 0, "伤害": 0, "治疗": 0, "锁定": 0, "打断": 0, "段数": 0})
                            box["治疗"] += healed
                            if "首次出手" not in unit and healed:
                                unit["首次出手"] = now
                finally:
                    spec.formula = saved
                for effect, delay, hint in _effects(spec, "命中", contract["effect_specs"]):
                    who = unit if effect.direction == "治疗" or spec.heal_formula else target
                    who = _effect_target(unit, who, hint)
                    wait = float(delay or 0)
                    if wait > 0:
                        events.append((now + wait, "施加效果", unit, effect, who))
                    else:
                        _apply_effect(host, unit, who, effect, now, events, gaps)
                if spec.pay_at == "命中":
                    _pay(unit, spec)
                if spec.refund_resource and spec.refund is not None and spec.refund_at in (None, "命中"):
                    unit["资源"][spec.refund_resource] = unit["资源"].get(spec.refund_resource, 0) + spec.refund
            continue
        if unit.get("施法"):
            unit["施法"] = None
        strategy = strategies.get(unit.get("行为"), {})
        if not mode:
            mode = str(strategy.get("择技方式") or "")
        rules = [r for r in contract.get("rules") or [] if str(r.get("策略名") or "") == unit.get("行为")]
        _resource_extrema(unit)
        _track_threat(units, now)
        mistake = _num(task.get("失误率"))
        if mistake is None:
            mistake = _num(params.get("失误率"))
        if mistake is None:
            mistake = _num(params.get("失误率默认"))
        if mistake is not None and mistake > 1:
            mistake = mistake / 100.0
        interval = _num(strategy.get("决策间隔"))
        if interval is None:
            interval = _num(params.get("决策间隔默认"))
        if interval is None:
            gaps.append(f"「{unit['名称']}」的策略没有决策间隔，模拟参数也没有默认值")
            interval = step_ms
        switch_pen = unit.pop("锁定切换惩罚", None)
        if switch_pen:
            interval = float(interval) + float(switch_pen)
        if mistake and rng.random() < float(mistake):
            _bump(unit, "失误次数", 1)
            _bump(unit, "决策延迟累计", interval)
            events.append((now + interval, "决策", unit))
            continue
        action = choose(unit, rules, strategy, units, arena, now, mode, contract.get("matrices") or {}, gaps)
        if action is None:
            if any(_ready(unit, spec, now, False) for spec in unit["技能规格"].values()):
                _bump(unit, "就绪空转", interval)
            events.append((now + interval, "决策", unit))
            continue
        if action[0] == "脱战":
            strategy = action[1]
            _bump(unit, "脱战次数", 1)
            if str(strategy.get("脱战回满") or "") == "是":
                unit["生命值"] = unit["开场生命"]
                unit["资源"] = dict(unit["开场资源"])
            if str(strategy.get("脱战阶段处理") or "") == "脱战重置":
                unit["阶段"] = str(strategy.get("初始阶段") or unit.get("阶段"))
            events.append((now + interval, "决策", unit))
            continue
        if action[0] == "回活动范围":
            speed = _speed(unit, contract.get("transfers") or {}, gaps, None)
            home = unit.get("出生点")
            if speed and home:
                hx, hy = home
                x, y = arena.pos[unit["名称"]]
                dist = ((hx - x) ** 2 + (hy - y) ** 2) ** 0.5
                step = min(dist, speed * interval / 1000)
                if dist:
                    arena.pos[unit["名称"]] = (x + (hx - x) / dist * step, y + (hy - y) / dist * step)
                    _bump(unit, "移动距离", step)
                    _bump(unit, "走位毫秒", interval)
            events.append((now + interval, "决策", unit))
            continue
        if action[0] == "黑板":
            rule = action[1]
            unit.setdefault("黑板", {})[str(rule.get("黑板键"))] = rule.get("黑板值")
            _mark_rule(unit, rule, now)
            if str(rule.get("条件1类型") or "") == "开战":
                unit["_开战已用"] = True
            events.append((now + interval, "决策", unit))
            continue
        if action[0] == "进阶段":
            rule = action[1]
            next_phase = rule.get("目标阶段")
            if next_phase in (None, ""):
                next_phase = "P2"
            unit["阶段"] = str(next_phase)
            _mark_rule(unit, rule, now)
            unit.setdefault("黑板", {})["BattleState"] = 2 if str(next_phase) == "P2" else 1
            if "阶段切换毫秒" not in unit:
                unit["阶段切换毫秒"] = now
            log.append({"时间": now, "施法者": unit["名称"], "动作": "进阶段", "目标": str(next_phase), "伤害": 0, "治疗": 0})
            events.append((now + interval, "决策", unit))
            continue
        if action[0] == "靠近":
            target, meters, rule = action[1], action[2], action[3]
            speed = _speed(unit, contract.get("transfers") or {}, gaps, (rule or {}).get("移动方式"))
            if not speed:
                events.append((now + interval, "决策", unit))
                continue
            _step_move(unit, arena, target["名称"], min(meters, speed * interval / 1000))
            _bump(unit, "走位毫秒", interval)
            _bump(unit, "距离和", arena.distance(unit["名称"], target["名称"]))
            _bump(unit, "距离次", 1)
            log.append({"时间": now, "施法者": unit["名称"], "动作": "靠近", "目标": target["名称"], "伤害": 0, "治疗": 0})
            events.append((now + interval, "决策", unit))
            continue
        spec, target, rule = action[1], action[2], action[3]
        if target is None:
            events.append((now + interval, "决策", unit))
            continue
        _rewrite(unit, spec, target, "施放", rng, gaps)
        segments, piece, first = _segments(spec, gaps)
        swing = (spec.chant or 0) + (spec.action or 0)
        unit["施法"] = (spec, target)
        unit["吟唱直到"] = now + (spec.chant or 0)
        unit["施法直到"] = now + swing
        gcd = spec.gcd
        if gcd is None:
            gcd = _num(params.get("公共冷却默认"))
        if gcd is None:
            gaps.append(f"技能「{spec.name}」没有公共冷却时长，模拟参数也没有公共冷却默认")
            gcd = 0
        unit["公共冷却直到"] = now + swing + gcd
        unit["冷却"][spec.name] = now + swing + (spec.channel or 0) + (spec.cooldown or 0)
        _pay(unit, spec)
        _resource_extrema(unit)
        _bump(unit, "动作锁", swing + (spec.channel or 0))
        _bump(unit, "吟唱占用", spec.chant or 0)
        _bump(unit, "公共冷却占用", gcd or 0)
        box = unit.setdefault("技能统计", {}).setdefault(
            spec.name, {"次数": 0, "伤害": 0, "治疗": 0, "锁定": 0, "打断": 0, "段数": 0,
                        "命中段": 0, "暴击段": 0, "未中段": 0, "主目标伤害": 0, "溅射伤害": 0, "浪费CD": 0}
        )
        prev_end = box.get("上次结束")
        cd_ms = (spec.cooldown or 0)
        box["冷却"] = cd_ms
        if prev_end is not None and cd_ms:
            ready_at = float(prev_end) + float(cd_ms)
            if now > ready_at:
                box["浪费CD"] = box.get("浪费CD", 0) + (now - ready_at)
        box["次数"] += 1
        box["锁定"] += swing + (spec.channel or 0) + (gcd or 0)
        box["上次结束"] = now + swing + (spec.channel or 0)
        if target["名称"] in arena.pos and unit["名称"] in arena.pos:
            _bump(unit, "距离和", arena.distance(unit["名称"], target["名称"]))
            _bump(unit, "距离次", 1)
        if spec.dash_distance and spec.dash_speed and spec.dash_speed > 0:
            _bump(unit, "位移次数", 1)
            duration = spec.dash_distance / spec.dash_speed * 1000
            steps = max(1, int(round(duration / step_ms))) if step_ms else 1
            each = spec.dash_distance / steps
            for index in range(steps):
                events.append((now + duration * (index + 1) / steps, "位移", unit, target, each))
        for effect, delay, hint in _effects(spec, "施放", contract["effect_specs"]):
            who = _effect_target(unit, target, hint)
            wait = float(delay or 0)
            if wait > 0:
                events.append((now + wait, "施加效果", unit, effect, who))
            else:
                _apply_effect(host, unit, who, effect, now, events, gaps)
        _summon(unit, spec, now, arena, units, events)
        for index in range(segments):
            events.append((now + first + piece * index, "命中", unit, spec, target))
        events.append((max(unit["公共冷却直到"], now + first + piece * max(0, segments - 1)), "决策", unit))
        if rule is not None:
            _mark_rule(unit, rule, now)
            if rule.get("黑板键") not in (None, ""):
                unit.setdefault("黑板", {})[str(rule.get("黑板键"))] = rule.get("黑板值")
        log.append({"时间": now, "施法者": unit["名称"], "动作": "开始施法", "目标": spec.name, "伤害": 0, "治疗": 0})
    for unit in units:
        opened = sum(float(v) for v in (unit.get("开场资源") or {}).values() if isinstance(v, (int, float)))
        left = sum(float(v) for v in (unit.get("资源") or {}).values() if isinstance(v, (int, float)))
        if left > opened:
            unit["溢出"] = left - opened
    phase_ms = None
    for unit in units:
        if unit.get("阶段切换毫秒") is not None:
            phase_ms = unit["阶段切换毫秒"]
            break
    return {"时长毫秒": min(now, limit_ms), "单位": units, "日志": log, "待对齐": gaps, "阶段切换毫秒": phase_ms}
