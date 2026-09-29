"""出手：规则优先时按优先级执行第一条成立的规则。推演时才在合法技能里比单位时间收益。"""
from __future__ import annotations

from 战斗模拟.sim.engage import apply_hit
from 战斗模拟.sim.spec import SkillSpec


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ready(unit, spec: SkillSpec, now: float, force: bool) -> bool:
    if force:
        return True
    if now < unit["冷却"].get(spec.name, 0) or now < unit["公共冷却直到"]:
        return False
    if spec.resource and spec.cost is not None:
        if unit["资源"].get(spec.resource, 0) < spec.cost:
            unit["打不起"] = unit.get("打不起", 0) + 1
            return False
    if "禁止法术" in unit.get("状态", ()) and spec.value_type == "魔法":
        return False
    if "硬直" in unit.get("状态", ()):
        return False
    return True


def _in_range(unit, spec: SkillSpec, arena, target) -> bool:
    if spec.need_target == "否" or spec.max_range is None or target is None:
        return True
    dist = arena.distance(unit["名称"], target["名称"])
    near = spec.min_range or 0
    return near <= dist <= spec.max_range


def _facing_ok(unit, target, arena) -> bool:
    """面向角：攻方朝向与目标夹角不超过半锥。缺参则不卡。"""
    params = unit.get("_params") or {}
    half = _num(params.get("面向角"))
    if half is None or target is None:
        return True
    if unit["名称"] not in arena.pos or target["名称"] not in arena.pos:
        return True
    import math
    ax, ay = arena.pos[unit["名称"]]
    bx, by = arena.pos[target["名称"]]
    want = math.atan2(by - ay, bx - ax)
    have = arena.facing.get(unit["名称"], want)
    delta = abs((want - have + math.pi) % (2 * math.pi) - math.pi)
    return delta <= math.radians(half)


def _target_of(unit, rule, units, arena):
    name = str(rule.get("目标") or "")
    foes = [u for u in units if u["阵营"] != unit["阵营"] and u["生命值"] > 0 and "不可选中" not in u.get("标记", ()) and "不可选中" not in u.get("状态", ())]
    allies = [u for u in units if u["阵营"] == unit["阵营"] and u["生命值"] > 0]
    if name == "生命值最低":
        pool = allies or [unit]
        return min(pool, key=lambda u: u["生命值"] / u["生命上限"] if u["生命上限"] else 1)
    if name == "当前仇恨":
        table = unit.get("仇恨表") or {}
        if table and foes:
            hated = max(foes, key=lambda u: table.get(u["名称"], 0))
            if table.get(hated["名称"], 0) > 0:
                return hated
        if foes:
            return min(foes, key=lambda u: arena.distance(unit["名称"], u["名称"]))
    return foes[0] if foes else None


def _compare(left, op: str, right) -> bool:
    if right is None:
        return False
    if op == "≤":
        return left <= right
    if op == "≥":
        return left >= right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    return left == right


def _condition(unit, rule, now: float, units=None, arena=None) -> bool:
    kind = str(rule.get("条件1类型") or "")
    if not kind:
        return True
    if kind == "开战":
        return not unit.get("_开战已用")
    if kind == "冷却就绪":
        return True
    if kind == "生命%":
        subject = str(rule.get("条件1对象") or "")
        if subject not in ("", "自身生命%"):
            return False
        left = unit["生命值"] / unit["生命上限"] * 100 if unit["生命上限"] else 0
        return _compare(left, str(rule.get("条件1比较") or ""), _num(rule.get("条件1值")))
    if kind == "距离":
        subject = str(rule.get("条件1对象") or "")
        if subject not in ("", "目标距离") or arena is None or not units:
            return False
        foes = [u for u in units if u["阵营"] != unit["阵营"] and u["生命值"] > 0]
        if not foes:
            return False
        foe = min(foes, key=lambda u: arena.distance(unit["名称"], u["名称"]))
        left = arena.distance(unit["名称"], foe["名称"])
        return _compare(left, str(rule.get("条件1比较") or ""), _num(rule.get("条件1值")))
    if kind == "黑板":
        key = str(rule.get("条件1对象") or rule.get("黑板键") or "")
        if not key:
            return False
        left = (unit.get("黑板") or {}).get(key)
        right = rule.get("条件1值")
        op = str(rule.get("条件1比较") or "")
        if op in ("", "=", "=="):
            return str(left) == str(right)
        try:
            return _compare(float(left), op, _num(right))
        except (TypeError, ValueError):
            return False
    return False


def choose(unit, rules, strategy: dict, units, arena, now: float, mode: str, matrices, gaps):
    foes = [u for u in units if u["阵营"] != unit["阵营"] and u["生命值"] > 0]
    if strategy.get("初始阶段") and unit.get("阶段") in (None, "", "P1") and not unit.get("_阶段已初始化"):
        unit["阶段"] = str(strategy.get("初始阶段"))
        unit["_阶段已初始化"] = True
    origin = unit.get("出生点")
    if origin is None and unit["名称"] in arena.pos:
        unit["出生点"] = arena.pos[unit["名称"]]
    if foes:
        foe = _locked_target(unit, foes, strategy, arena, now)
        dist = arena.distance(unit["名称"], foe["名称"])
        leash = _num(strategy.get("脱战距离"))
        if leash is not None and dist > leash:
            return ("脱战", strategy)
        home = unit.get("出生点")
        activity = _num(strategy.get("活动范围"))
        if home is not None and activity is not None:
            hx, hy = home
            x, y = arena.pos[unit["名称"]]
            if ((x - hx) ** 2 + (y - hy) ** 2) ** 0.5 > activity:
                return ("回活动范围", strategy)
    enrage = _num(strategy.get("狂暴时限"))
    if enrage is not None and now >= enrage * 1000:
        unit.setdefault("标记", set()).add("狂暴")
    ordered = sorted(
        rules,
        key=lambda r: ((_num(r.get("优先级")) or 0), _num(r.get("权重")) or 0, 1 if str(r.get("轴") or "") == "剧本" else 0),
        reverse=True,
    )
    if mode in ("规则", "规则优先"):
        for rule in ordered:
            if str(rule.get("启用") or "是") == "否":
                continue
            phase = str(rule.get("阶段") or "")
            if phase and phase != unit.get("阶段"):
                continue
            limit = _num(rule.get("执行次数上限"))
            used = unit["规则次数"].get(rule.get("规则名"), 0)
            if limit is not None and used >= limit:
                continue
            until = (unit.get("规则冷却直到") or {}).get(rule.get("规则名"))
            if until is not None and now < until:
                continue
            if not _condition(unit, rule, now, units, arena):
                continue
            action = str(rule.get("动作") or "")
            if action == "写黑板":
                return ("黑板", rule)
            if action == "进阶段":
                return ("进阶段", rule)
            if action == "移动":
                target = _target_of(unit, rule, units, arena)
                if target is None:
                    continue
                gap = arena.distance(unit["名称"], target["名称"])
                if gap <= 0:
                    continue
                return ("靠近", target, gap, rule)
            if action != "使用技能":
                continue
            spec = unit["技能规格"].get(str(rule.get("技能") or ""))
            if spec is None:
                continue
            target = _target_of(unit, rule, units, arena)
            force = str(rule.get("强制施放") or "") == "是"
            if not _ready(unit, spec, now, force):
                continue
            if not _in_range(unit, spec, arena, target):
                gap = None
                if target is not None and spec.max_range is not None:
                    gap = arena.distance(unit["名称"], target["名称"]) - spec.max_range
                if gap and gap > 0:
                    # 追击距离是野外索敌半径。对阵里目标已经锁定，贴脸只受脱战距离和活动范围约束。
                    if str(rule.get("朝向") or "") == "面敌":
                        arena.move(unit["名称"], target["名称"], 0)
                    return ("靠近", target, gap, rule)
                continue
            if target is not None and not _facing_ok(unit, target, arena):
                arena.move(unit["名称"], target["名称"], 0)
                if not _facing_ok(unit, target, arena):
                    return ("靠近", target, 0.01, rule)
            return ("技能", spec, target, rule)
        if not rules:
            return _by_value(unit, units, arena, now, matrices, gaps)
        return None
    return _by_value(unit, units, arena, now, matrices, gaps)


def _locked_target(unit, foes, strategy, arena, now):
    lock = _num(strategy.get("锁定时长"))
    current = unit.get("锁定目标")
    until = unit.get("锁定直到") or 0
    if current and lock and now < until:
        alive = next((u for u in foes if u["名称"] == current), None)
        if alive and str(strategy.get("换目标条件") or "") == "不换":
            return alive
    chase = _num(strategy.get("追击距离"))
    if chase is not None:
        near = [u for u in foes if arena.distance(unit["名称"], u["名称"]) <= chase]
        if near:
            foes = near
    foe = min(foes, key=lambda u: arena.distance(unit["名称"], u["名称"]))
    if str(strategy.get("默认目标") or "") == "生命值最低":
        foe = min(foes, key=lambda u: u["生命值"])
    elif str(strategy.get("默认目标") or "") == "当前仇恨":
        table = unit.get("仇恨表") or {}
        if any(table.get(u["名称"], 0) for u in foes):
            foe = max(foes, key=lambda u: table.get(u["名称"], 0))
    unit["锁定目标"] = foe["名称"]
    if lock:
        unit["锁定直到"] = now + lock
    if current and current != foe["名称"]:
        params = unit.get("_params") or {}
        penalty = _num(params.get("目标切换惩罚"))
        if penalty:
            unit["决策延迟累计"] = unit.get("决策延迟累计", 0) + penalty
            unit["锁定切换惩罚"] = penalty
    return foe


def _by_value(unit, units, arena, now, matrices, gaps):
    """推演：用技能解析式除以锁定时间。优先级只在数值相同时比较。"""
    from 战斗模拟.sim.expr import 求值
    from 战斗模拟.sim.flow import _stats

    best = None
    best_score = None
    foes = [u for u in units if u["阵营"] != unit["阵营"] and u["生命值"] > 0]
    if not foes:
        return None
    target = min(foes, key=lambda u: arena.distance(unit["名称"], u["名称"]))
    for spec in unit["技能规格"].values():
        if not _ready(unit, spec, now, False):
            continue
        if not _in_range(unit, spec, arena, target):
            if spec.max_range is not None:
                gap = arena.distance(unit["名称"], target["名称"]) - spec.max_range
                if gap > 0 and best is None:
                    best = ("靠近", target, gap, None)
            continue
        amount = 求值(spec.formula, _stats(unit), _stats(target)) if spec.formula else 0
        lock_time = (spec.chant or 0) + (spec.action or 0) + (spec.channel or 0)
        if lock_time <= 0:
            gaps.append(f"技能「{spec.name}」没有吟唱、动作或引导，推演无法除以锁定时间")
            continue
        score = amount / lock_time
        priority = spec.priority or 0
        current = best[1].priority or 0 if best and best[0] == "技能" else -1
        if best_score is None or score > best_score or (score == best_score and priority > current):
            best_score = score
            best = ("技能", spec, target, None)
    return best
