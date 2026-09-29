"""一次命中或治疗走战斗流程，不在流程外再乘攻击除以防御。"""
from __future__ import annotations

from 战斗模拟.sim.expr import 求值
from 战斗模拟.sim.flow import FlowHost, _stats


def _bag(unit) -> dict:
    data = _stats(unit)
    data.setdefault("等级", unit.get("等级") or data.get("等级"))
    return data


def _once(gaps: list[str], text: str) -> None:
    if text not in gaps:
        gaps.append(text)


def build_env(attacker, defender, skill, matrices: dict, gaps: list[str], origin: str = "直接") -> dict:
    atk = _bag(attacker)
    dfd = _bag(defender)
    spec = skill
    kind = spec.value_type or ""
    channel = "魔法" if kind == "魔法" else "物理"
    tags = spec.tags or ""
    if "普攻" in tags or (spec.kind == "普攻"):
        action = "普攻"
    else:
        action = "技能"
    # SimC 式：标签优先；否则按最大距离推断，避免缺标签刷屏
    style = "近战" if "近战" in tags else "远程" if "远程" in tags else None
    if style is None:
        if spec.max_range is not None:
            style = "近战" if float(spec.max_range) <= 3.0 else "远程"
            _once(gaps, f"技能「{spec.name}」标签无近战/远程，已按最大距离{spec.max_range}推断为{style}")
        else:
            weapon = str(attacker.get("武器") or spec.weapon or "")
            melee_weapons = {"剑盾", "大剑", "长枪", "短剑", "拳套", "巨斧", "鞭子", "空手", "盾杖"}
            if weapon in melee_weapons:
                style = "近战"
            elif weapon:
                style = "远程"
            if style:
                _once(gaps, f"技能「{spec.name}」标签无近战/远程，已按武器「{weapon}」推断为{style}")
    weapon = attacker.get("武器") or spec.weapon
    element = spec.element if spec.element_from == "强制" else None
    if spec.formula and spec.element_from is None and spec.element:
        _once(gaps, f"技能「{spec.name}」写了元素但没有元素来源，克制不会使用这个元素")
    matrix = 1.0
    if spec.use_element == "是" and element:
        defense = defender.get("防御元素")
        # 无/空防御按无元素行
        defense_key = defense if defense not in (None, "", "无") else "无元素"
        if isinstance(defense_key, (int, float)):
            _once(gaps, f"守方防御元素是数字「{defense_key}」，流派档案可能读错列，这次不乘克制")
        else:
            table = ((matrices or {}).get("元素") or {}).get(str(defense_key)) or {}
            if element not in table:
                _once(gaps, f"元素克制表没有「{element}」对「{defense_key}」，技能「{spec.name}」这次不乘克制")
            else:
                matrix = float(table[element])
    size_factor = 1.0
    body_raw = defender.get("体型")
    body_aliases = {
        "中体型": "中体型", "大体型": "大体型", "小体型": "小体型",
        "中型": "中体型", "大型": "大体型", "小型": "小体型",
    }
    body_name = body_aliases.get(str(body_raw).strip()) if body_raw not in (None, "") else None
    if body_raw not in (None, "") and body_name is None:
        _once(gaps, f"体型「{body_raw}」对不上小体型/中体型/大体型")
    if spec.use_size == "是":
        weapon_name = str(weapon or "")
        table = ((matrices or {}).get("体型") or {}).get(weapon_name) or {}
        if not weapon_name:
            _once(gaps, f"技能「{spec.name}」参与体型克制但攻方没有武器类型")
        elif body_name is None:
            pass
        elif body_name not in table:
            _once(gaps, f"体型克制表没有武器「{weapon_name}」对体型「{body_name}」")
        else:
            size_factor = float(table[body_name])
    size_name = {"中体型": "中型", "大体型": "大型", "小体型": "小型"}.get(body_name or "")
    race = defender.get("种族")

    def stat(bag, name, side):
        if name not in bag:
            return 0.0
        return bag[name]

    threat = spec.threat
    if threat is None and spec.formula:
        threat = 1.0
        _once(gaps, f"技能「{spec.name}」没有伤害仇恨系数，按 1.0 计（SimC 默认口径）")

    env = {
        "攻方": atk,
        "守方": dfd,
        "攻方等级": atk.get("等级"),
        "防方等级": dfd.get("等级"),
        "对应通道增伤": stat(atk, f"{channel}增伤%", "攻方"),
        "对应通道抗性": stat(dfd, f"{channel}抗性%", "守方"),
        "对应动作增伤": stat(atk, f"{action}增伤%", "攻方"),
        "对应动作抗性": stat(dfd, f"{action}抗性%", "守方"),
        "对应方式增伤": stat(atk, f"{style}增伤%", "攻方") if style else 0.0,
        "对应方式抗性": stat(dfd, f"{style}抗性%", "守方") if style else 0.0,
        "对应武器增伤": stat(atk, f"{weapon}增伤%", "攻方") if weapon else 0.0,
        "对应武器抗性": stat(dfd, f"{weapon}抗性%", "守方") if weapon else 0.0,
        "全武器增伤": stat(atk, "全武器增伤%", "攻方"),
        "全武器抗性": stat(dfd, "全武器抗性%", "守方"),
        "元素克制矩阵倍率": matrix,
        "对应元素增伤": stat(atk, f"{element}增伤%", "攻方") if element else 0.0,
        "对应元素抗性": stat(dfd, f"{element}抗性%", "守方") if element else 0.0,
        "全元素增伤": stat(atk, "全元素增伤%", "攻方"),
        "全元素抗性": stat(dfd, "全元素抗性%", "守方"),
        "对应种族增伤": stat(atk, f"{race}增伤%", "攻方") if race else 0.0,
        "对应种族抗性": stat(dfd, f"{race}抗性%", "守方") if race else 0.0,
        "全种族增伤": stat(atk, "全种族增伤%", "攻方"),
        "全种族抗性": stat(dfd, "全种族抗性%", "守方"),
        "武器体型修正系数": size_factor,
        "对应体型增伤": stat(atk, f"{size_name}增伤%", "攻方") if size_name else 0.0,
        "对应体型抗性": stat(dfd, f"{size_name}抗性%", "守方") if size_name else 0.0,
        "全体型增伤": stat(atk, "全体型增伤%", "攻方"),
        "全体型抗性": stat(dfd, "全体型抗性%", "守方"),
        "仇恨系数": threat if threat is not None else 0,
        "伤害类型": channel,
        "伤害来源": origin,
        "命中位": "必中" if spec.hit_rule == "必中" else spec.hit_rule,
        "暴击位": "不可暴击" if spec.crit_rule == "不可暴击" else spec.crit_rule,
    }
    if spec.formula and spec.hit_rule is None:
        _once(gaps, f"技能「{spec.name}」没有命中规则，闪避判定会按流程继续")
    return env


def _shield_left(unit) -> float:
    return sum(float(layer.get("剩余") or 0) for layer in (unit.get("护盾层") or []))


def apply_hit(host: FlowHost, attacker, defender, spec, matrices, gaps, origin: str = "直接") -> dict:
    before = defender["生命值"]
    atk_before = attacker["生命值"]
    shield_before = _shield_left(defender)
    amount = 求值(spec.formula, _bag(attacker), _bag(defender)) if spec.formula else 0
    env = build_env(attacker, defender, spec, matrices, gaps, origin)
    env["管线伤害"] = amount
    host.bind(attacker, defender, spec, env)
    host.env = env
    host.run("伤害")
    dealt = max(0.0, before - defender["生命值"])
    leech_var = host.var.get("吸血量")
    leech = float(leech_var) if isinstance(leech_var, (int, float)) else max(0.0, attacker["生命值"] - atk_before)
    reflect_var = host.var.get("反伤量")
    reflect = float(reflect_var) if isinstance(reflect_var, (int, float)) else max(0.0, atk_before - attacker["生命值"])
    blocked = host.var.get("格挡减免量")
    block_amount = float(blocked) if isinstance(blocked, (int, float)) else 0.0
    final = host.var.get("最终伤害")
    overkill = max(0.0, float(final) - dealt) if isinstance(final, (int, float)) else 0.0
    threat = host.var.get("伤害仇恨")
    if isinstance(threat, (int, float)) and threat:
        table = attacker.setdefault("仇恨表", {})
        table[defender["名称"]] = table.get(defender["名称"], 0) + float(threat)
    return {
        "伤害": dealt,
        "吸血": max(0.0, leech),
        "反伤": max(0.0, reflect),
        "闪避": "已闪避" in host.marks,
        "暴击": "已暴击" in host.marks,
        "格挡": block_amount > 0 or "已格挡" in host.marks,
        "格挡减免": block_amount,
        "护盾吸收": max(0.0, shield_before - _shield_left(defender)),
        "过量击杀": overkill,
        "减伤减免": max(0.0, float(amount) - float(final)) if isinstance(final, (int, float)) else 0.0,
        "来源": origin,
    }


def apply_heal(host: FlowHost, caster, target, spec, gaps) -> float:
    before = target["生命值"]
    amount = 求值(spec.heal_formula, _bag(caster), _bag(target)) if spec.heal_formula else 0
    env = {
        "攻方": _bag(caster),
        "守方": _bag(target),
        "攻方等级": _bag(caster).get("等级"),
        "防方等级": _bag(target).get("等级"),
        "治疗值": amount,
        "暴击位": "不可暴击",
        "仇恨系数": spec.threat if spec.threat is not None else 0,
    }
    host.bind(caster, target, spec, env)
    host.env = env
    host.target = target
    host.run("治疗")
    gained = max(0.0, target["生命值"] - before)
    return gained
