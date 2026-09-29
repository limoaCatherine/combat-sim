"""旧的攻击/(攻击+防御)已经撤掉。命中请走战斗流程。"""
from __future__ import annotations


def hit_damage(*_args, **_kwargs):
    raise RuntimeError("伤害请走战斗流程，不再使用攻击/(攻击+防御)")


def hit_heal(*_args, **_kwargs):
    raise RuntimeError("治疗请走战斗流程")


def _num(row, key, default=None):
    value = row.get(key) if isinstance(row, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _yes(value) -> bool:
    return str(value or "").strip() == "是"
