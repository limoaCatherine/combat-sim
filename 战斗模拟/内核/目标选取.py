"""多目标选取（SimC 风格最小规则）：单体 / 数量上限 cleave / 次要目标规则。

AoE 不另开管线——路由层对本函数返回的每个目标 id 各调一次伤害/治疗/异常/驱散 pipe。
"""
from __future__ import annotations

import logging
import math
import random
from typing import Any, Mapping, Sequence

from 战斗模拟.模型.实体 import 实体

_log = logging.getLogger("战斗模拟.目标选取")
_RADIUS_WARNED = False


def _行取值(技能行: Any, *键名: str, 默认: Any = None) -> Any:
    if 技能行 is None:
        return 默认
    if isinstance(技能行, Mapping):
        for k in 键名:
            if k in 技能行 and 技能行[k] not in (None, ""):
                return 技能行[k]
        raw = 技能行.get("原始行")
        if isinstance(raw, Mapping):
            for k in 键名:
                if k in raw and raw[k] not in (None, ""):
                    return raw[k]
        return 默认
    for k in 键名:
        v = getattr(技能行, k, None)
        if v not in (None, ""):
            return v
    raw = getattr(技能行, "原始行", None)
    if isinstance(raw, Mapping):
        for k in 键名:
            if k in raw and raw[k] not in (None, ""):
                return raw[k]
    return 默认


def _转浮点(v: Any, 默认: float) -> float:
    if v is None or str(v).strip() in ("", "—", "-", "无", "None"):
        return 默认
    try:
        return float(v)
    except (TypeError, ValueError):
        return 默认


def _转整数(v: Any, 默认: int) -> int:
    if v is None or str(v).strip() in ("", "—", "-", "无", "None"):
        return 默认
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 默认


def _存活(e: 实体) -> bool:
    if getattr(e, "存活", True) is False:
        return False
    try:
        return float(getattr(e, "生命", 0) or 0) > 0
    except (TypeError, ValueError):
        return True


def _取位置(e: 实体) -> tuple[float, float] | None:
    """实体可选坐标：位置=(x,y) 或 位置x/位置y；均无则 None。"""
    pos = getattr(e, "位置", None)
    if pos is not None:
        try:
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return float(pos[0]), float(pos[1])
            if isinstance(pos, Mapping) and "x" in pos and "y" in pos:
                return float(pos["x"]), float(pos["y"])
        except (TypeError, ValueError):
            pass
    x = getattr(e, "位置x", None)
    y = getattr(e, "位置y", None)
    if x is not None and y is not None:
        try:
            return float(x), float(y)
        except (TypeError, ValueError):
            return None
    # 面板兜底
    panel = getattr(e, "面板", None) or {}
    if isinstance(panel, Mapping):
        px, py = panel.get("位置x"), panel.get("位置y")
        if px is not None and py is not None:
            try:
                return float(px), float(py)
            except (TypeError, ValueError):
                return None
    return None


def _距离(a: 实体, b: 实体) -> float | None:
    pa, pb = _取位置(a), _取位置(b)
    if pa is None or pb is None:
        return None
    return math.hypot(pa[0] - pb[0], pa[1] - pb[1])


def _解析主目标(
    主目标: 实体 | str | None,
    实体表: dict[str, 实体],
) -> 实体 | None:
    if 主目标 is None:
        return None
    if isinstance(主目标, 实体):
        return 主目标
    return 实体表.get(str(主目标))


def 选取目标(
    攻方: 实体,
    主目标: 实体 | str | None,
    实体列表: Sequence[实体],
    技能行: Any = None,
    *,
    rng: random.Random | None = None,
) -> list[str]:
    """按技能行规则选出有序目标 id 列表。

    规则（最小 SimC-like）：
    - 过滤死亡
    - 目标数量上限 N（缺省 1 = 单体）；主目标优先占一席
    - 次要目标规则：最近 / 生命最低 / 生命最高 / 随机（缺省最近）
    - 光环半径：若实体有坐标则按距攻方过滤；无坐标则忽略半径并只告警一次
    """
    global _RADIUS_WARNED
    实体表 = {e.id: e for e in 实体列表 if e is not None}
    # 也纳入攻方/主目标（可能不在列表里）
    if 攻方 is not None:
        实体表.setdefault(攻方.id, 攻方)
    primary = _解析主目标(主目标, 实体表)
    if primary is not None:
        实体表.setdefault(primary.id, primary)

    上限 = max(1, _转整数(_行取值(技能行, "目标数量上限", "目标数"), 1))
    规则 = str(
        _行取值(技能行, "次要目标规则", "选择规则", 默认="最近") or "最近"
    ).strip()
    半径 = _转浮点(_行取值(技能行, "光环半径", "溅射半径"), 0.0)

    candidates = [e for e in 实体表.values() if e.id != 攻方.id and _存活(e)]
    stype = str(_行取值(技能行, "技能类型", "类型", 默认="") or "")
    heal_pipe = str(_行取值(技能行, "治疗管线", 默认="") or "")
    want_ally = (
        "治疗" in stype
        or bool(heal_pipe)
        or _行取值(技能行, "基础治疗") is not None
        or str(_行取值(技能行, "目标阵营", 默认="") or "") in ("友方", "友军", "ally")
    )
    if want_ally:
        allies = [e for e in candidates if getattr(e, "阵营", "") == getattr(攻方, "阵营", "")]
        if allies:
            candidates = allies
        if primary is not None and primary.id == 攻方.id:
            candidates = [攻方] + [c for c in candidates if c.id != 攻方.id]
    else:
        foes = [e for e in candidates if getattr(e, "阵营", "") != getattr(攻方, "阵营", "")]
        if foes:
            candidates = foes

    if 半径 > 0:
        has_any_pos = any(_取位置(e) is not None for e in candidates + [攻方])
        if not has_any_pos:
            if not _RADIUS_WARNED:
                _log.warning(
                    "光环半径=%.3f 但实体无位置坐标，忽略半径过滤（只提示一次）",
                    半径,
                )
                _RADIUS_WARNED = True
        else:
            filtered: list[实体] = []
            for e in candidates:
                d = _距离(攻方, e)
                if d is None or d <= 半径:
                    filtered.append(e)
            candidates = filtered

    out: list[str] = []
    if primary is not None and _存活(primary) and primary.id in {c.id for c in candidates}:
        out.append(primary.id)
    elif primary is not None and _存活(primary):
        # 主目标可能因阵营过滤被踢；单体/首目标仍强制纳入
        out.append(primary.id)

    if 上限 <= 1:
        return out[:1] if out else ([candidates[0].id] if candidates else [])

    rest = [e for e in candidates if e.id not in out]
    rnd = rng or random.Random(0)

    def _sort_key_nearest(e: 实体) -> tuple:
        d = _距离(攻方, e)
        # 无坐标：保持相对列表序（用原 candidates 下标）
        if d is None:
            try:
                idx = next(i for i, c in enumerate(candidates) if c.id == e.id)
            except StopIteration:
                idx = 0
            return (1, idx, e.id)
        return (0, d, e.id)

    if 规则 in ("生命最低", "最低生命", "lowest_hp", "lowest"):
        rest.sort(key=lambda e: (float(e.生命), e.id))
    elif 规则 in ("生命最高", "最高生命", "highest_hp", "highest"):
        rest.sort(key=lambda e: (-float(e.生命), e.id))
    elif 规则 in ("随机", "random"):
        rnd.shuffle(rest)
    else:
        # 最近（默认）
        rest.sort(key=_sort_key_nearest)

    for e in rest:
        if len(out) >= 上限:
            break
        out.append(e.id)
    return out


# 英文别名
select_targets = 选取目标
