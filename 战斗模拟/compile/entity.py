"""把构筑或怪物编译成可战斗的实体。缺生命则拒绝，不补默认血量。"""
from __future__ import annotations


class MissingLife(RuntimeError):
    pass


def _num(value, default=0.0) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if value in (None, ""):
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


def parse_override(text) -> dict[str, float]:
    out = {}
    if not text:
        return out
    for part in str(text).split(";"):
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        out[key.strip()] = _num(raw)
    return out


def _skills_of(build: dict, catalog: dict) -> list[dict]:
    names = []
    basic = build.get("普攻技能")
    if basic:
        names.append(str(basic))
    for i in range(1, 9):
        name = build.get(f"技能{i}")
        if name:
            names.append(str(name))
    out = []
    for name in names:
        row = catalog.get(name)
        if row:
            out.append(row)
    return out


def resources_of(stats: dict) -> dict[str, float]:
    """只收录面板上真正有的资源。没有初始值就不建池。"""
    out = {}
    for name in ("怒气", "能量", "魔法值"):
        if f"{name}初始值" in stats:
            out[name] = float(stats[f"{name}初始值"])
        elif name in stats:
            out[name] = float(stats[name])
    return out


def _pool_name(kind) -> str | None:
    text = str(kind or "").strip()
    if text in ("魔法", "魔法值"):
        return "魔法值"
    if text in ("能量", "怒气"):
        return text
    return None


def _bind_resource(skill: dict, pool: str | None, gaps: list[str]) -> dict:
    row = dict(skill)
    if not pool:
        return row
    for key in ("主消耗资源", "回复资源"):
        current = row.get(key)
        if current and current != pool and not (pool == "魔法值" and current == "魔法"):
            gaps.append(f"技能「{row.get('技能名')}」的{key}是「{current}」，流派施法资源是「{pool}」")
    return row


def _apply_mastery(skills: list[dict], points: str, nodes: list[dict]) -> list[dict]:
    wanted = {part.strip() for part in str(points or "").replace(";", "；").split("；") if part.strip()}
    if not wanted:
        return skills
    copied = [dict(s) for s in skills]
    by_name = {str(s.get("技能名")): s for s in copied}
    for node in nodes:
        if str(node.get("节点名") or "") not in wanted:
            continue
        if str(node.get("改写时机") or "开战") not in ("开战", ""):
            continue
        field = str(node.get("目标字段") or "")
        op = str(node.get("运算") or "")
        targets = str(node.get("目标技能") or "").replace(";", "；").split("；")
        for target in targets:
            skill = by_name.get(target.strip())
            if skill is None or not field:
                continue
            current = skill.get(field)
            number = node.get("数值")
            try:
                number = float(number)
            except (TypeError, ValueError):
                continue
            if field == "数值解析式" and isinstance(current, str):
                from 战斗模拟.sim.expr import 改系数
                skill[field] = 改系数(current, op, number)
            elif op == "加" and isinstance(current, (int, float)):
                skill[field] = float(current) + number
            elif op == "乘" and isinstance(current, (int, float)):
                skill[field] = float(current) * number
            elif op in ("设", "覆盖"):
                skill[field] = number
    return copied


def compile_player(build: dict, panel: dict[str, float], catalog: dict, profile: dict | None = None, mastery: list | None = None, gaps: list | None = None) -> dict:
    life = panel.get("生命值")
    if not life:
        raise MissingLife(f"{build.get('构筑名')} 开场面板没有生命值，模拟器不填默认血量")
    gaps = gaps if gaps is not None else []
    pool = _pool_name((profile or {}).get("施法资源类型"))
    skills = [_bind_resource(s, pool, gaps) for s in _skills_of(build, catalog)]
    skills = _apply_mastery(skills, build.get("精通点法"), mastery or [])
    points = {part.strip() for part in str(build.get("精通点法") or "").replace(";", "；").split("；") if part.strip()}
    on_hit = [
        node for node in (mastery or [])
        if str(node.get("节点名") or "") in points and str(node.get("改写时机") or "") == "命中时"
    ]
    on_cast = [
        node for node in (mastery or [])
        if str(node.get("节点名") or "") in points and str(node.get("改写时机") or "") == "施放时"
    ]
    return {
        "名称": str(build.get("构筑名")),
        "阵营": "A",
        "种类": "玩家",
        "等级": panel.get("等级"),
        "生命值": life,
        "生命上限": life,
        "属性": dict(panel),
        "技能": skills,
        "行为": str(build.get("行为配置") or build.get("构筑名") or ""),
        "资源": resources_of(panel),
        "武器": (profile or {}).get("武器类型"),
        "防御元素": (profile or {}).get("防御元素"),
        "体型": (profile or {}).get("体型"),
        "种族": (profile or {}).get("种族"),
        "默认移动状态": (profile or {}).get("默认移动状态"),
        "施法资源": pool,
        "命中精通": on_hit,
        "施放精通": on_cast,
    }


def compile_monster(row: dict, catalog: dict) -> dict:
    stats = parse_override(row.get("属性覆盖"))
    if row.get("等级") not in (None, "") and "等级" not in stats:
        stats["等级"] = _num(row.get("等级"))
    life = stats.get("生命值")
    if not life:
        raise MissingLife(f"怪物 {row.get('怪物名')} 没有生命，模拟器不填默认血量")
    names = [part.strip() for part in str(row.get("技能组") or "").replace("，", ",").split(",") if part.strip()]
    skills = [catalog[name] for name in names if name in catalog]
    return {
        "名称": str(row.get("怪物名")),
        "阵营": "B",
        "种类": "怪物",
        "生命值": life,
        "生命上限": life,
        "属性": stats,
        "技能": skills,
        "行为": str(row.get("行为配置") or ""),
        "资源": resources_of(stats),
        "武器": row.get("武器类型") or row.get("武器") or "空手",
        "防御元素": row.get("防御元素"),
        "体型": row.get("体型"),
        "种族": row.get("种族"),
        "施法资源": None,
        "命中精通": [],
        "等级": row.get("等级"),
    }
