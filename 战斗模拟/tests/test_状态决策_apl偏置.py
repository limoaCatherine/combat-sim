# -*- coding: utf-8 -*-
"""APL 弱偏置：不能覆盖明显更优技能；同分时打破平局。"""
from __future__ import annotations

from types import SimpleNamespace

from 战斗模拟.ai.状态决策 import 感知快照, 选择动作


def _sk(name: str, dmg: float, apl: float = 0, cond: str = "", slot: int = 0):
    return SimpleNamespace(
        名称=name,
        期望伤害=dmg,
        期望治疗=0.0,
        公共冷却毫秒=1000.0,
        吟唱毫秒=0.0,
        动作毫秒=0.0,
        占用GCD=True,
        栏位序=slot,
        APL优先级=apl,
        APL条件=cond,
        apl=apl,
        仇恨系数=1.0,
        伤害段="",
        治疗解析式="",
        段期望系数=1.0,
    )


def test_apl_alone_does_not_override_clearly_better_skill():
    snap = 感知快照(
        now_ms=0,
        self_hp=1000,
        self_hp_max=1000,
        target_hp=1000,
        target_hp_max=1000,
        gcd_ready_at=0,
        busy_until=0,
    )
    # 弱击期望伤极低但 APL 优先级极高；重击伤高
    weak = _sk("弱击", dmg=10.0, apl=999, cond="")
    strong = _sk("重击", dmg=200.0, apl=1, cond="")
    pick, detail = 选择动作(snap, [weak, strong], apl偏置=True, apl_epsilon=0.05)
    assert pick is not None
    assert pick.名称 == "重击", detail
    # APL 偏置应远小于伤吞吐差
    scores = {c["skill"]: c["score"] for c in detail["候选"]}
    assert scores["重击"] > scores["弱击"]


def test_apl_breaks_tie_when_scores_equal():
    snap = 感知快照(
        now_ms=0,
        self_hp=1000,
        self_hp_max=1000,
        target_hp=1000,
        target_hp_max=1000,
        gcd_ready_at=0,
        busy_until=0,
    )
    a = _sk("技能A", dmg=100.0, apl=1, cond="", slot=0)
    b = _sk("技能B", dmg=100.0, apl=50, cond="", slot=1)
    pick, detail = 选择动作(snap, [a, b], apl偏置=True, apl_epsilon=0.05)
    assert pick is not None
    assert pick.名称 == "技能B", detail
    scores = {c["skill"]: c for c in detail["候选"]}
    assert scores["技能B"]["apl"] > scores["技能A"]["apl"]


def test_apl_condition_gates_bias():
    snap = 感知快照(
        now_ms=0,
        self_hp=1000,
        self_hp_max=1000,
        target_hp=900,
        target_hp_max=1000,  # 90% — 斩杀条件不满足
        gcd_ready_at=0,
        busy_until=0,
    )
    finisher = _sk("斩杀", dmg=100.0, apl=100, cond="target_hp < 0.3", slot=0)
    filler = _sk("平砍", dmg=100.0, apl=1, cond="", slot=1)
    pick, detail = 选择动作(snap, [finisher, filler], apl偏置=True, apl_epsilon=0.05)
    assert pick is not None
    # 条件不匹配 → 斩杀无偏置，平砍栏位略低但仍可能因栏位序
    fin = next(c for c in detail["候选"] if c["skill"] == "斩杀")
    assert fin["apl"] == 0.0
