"""择技在 decide.py。这里只保留入口，避免再走写死的收益系数。"""
from __future__ import annotations

from 战斗模拟.sim.decide import choose


def choose_action(unit, rules, units, field, now, matrices, strategy=None, mode="规则", gaps=None):
    return choose(unit, rules, strategy or {}, units, field, now, mode, matrices, gaps if gaps is not None else [])
