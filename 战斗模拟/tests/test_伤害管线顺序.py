# -*- coding: utf-8 -*-
"""伤害管线阶段顺序与攻守侧向断言。"""
from __future__ import annotations

import random

from 战斗模拟.管道.伤害 import DAMAGE_PVE_STAGES, 解析伤害PVE


def test_stage_order_constant():
    assert DAMAGE_PVE_STAGES == (
        "无敌",
        "必中或必定闪避",
        "属性闪避",
        "免伤",
        "克制",
        "格挡",
        "暴击",
        "伤害乘区",
        "暴击伤害",
        "受伤修正",
        "吸血反伤",
    )


def test_executed_order_full_pipeline():
    out = 解析伤害PVE(
        基础伤害=100.0,
        attacker={"等级": 60, "命中%": 0.0, "精准": 0, "暴击": 0, "物理穿透": 0},
        defender={"等级": 60, "闪避%": 0.0, "物理防御": 0, "格挡": 0, "抗暴": 0},
        强制命中=True,
        rng=random.Random(0),
    )
    assert out["已执行阶段"] == list(DAMAGE_PVE_STAGES)
    assert "中间结果" in out
    for name in DAMAGE_PVE_STAGES:
        assert name in out["中间结果"], f"缺中间结果: {name}"


def test_invuln_stops_before_later_stages():
    out = 解析伤害PVE(基础伤害=100.0, defender={"标签": {"无敌"}})
    assert out["伤害"] == 0.0
    assert out["终止"] is True
    assert out["已执行阶段"] == ["无敌"]
    assert out["中间结果"]["无敌"]["触发"] is True


def test_must_dodge_unless_force_hit():
    out = 解析伤害PVE(
        基础伤害=100.0,
        defender={"标签": {"必定闪避"}},
        attacker={},
    )
    assert out["伤害"] == 0.0
    assert "必中或必定闪避" in out["已执行阶段"]

    out2 = 解析伤害PVE(
        基础伤害=100.0,
        defender={"标签": {"必定闪避"}},
        attacker={"标签": {"必中"}},
        强制命中=True,
        rng=random.Random(1),
    )
    assert out2["伤害"] > 0
    assert "属性闪避" in out2["已执行阶段"]


def test_mitigation_uses_defender_armor_attacker_pen():
    """免伤：守方防御 vs 攻方穿透（侧向）。"""
    base = 解析伤害PVE(
        基础伤害=1000.0,
        attacker={"等级": 60, "物理穿透": 0},
        defender={"等级": 60, "物理防御": 0},
        强制命中=True,
        禁止格挡=True,
        禁止暴击=True,
        rng=random.Random(0),
    )
    armored = 解析伤害PVE(
        基础伤害=1000.0,
        attacker={"等级": 60, "物理穿透": 0},
        defender={"等级": 60, "物理防御": 2000},
        强制命中=True,
        禁止格挡=True,
        禁止暴击=True,
        rng=random.Random(0),
    )
    assert armored["伤害"] < base["伤害"]
    assert armored["中间结果"]["免伤"]["免伤效果"] > 0


def test_block_mutex_crit():
    """格挡触发时不可暴击。"""
    out = 解析伤害PVE(
        基础伤害=100.0,
        attacker={"等级": 60, "精准率": 0.0, "暴击效果": 1.0},
        defender={"等级": 60, "格挡效果": 1.0, "格挡免伤%": 0.0},
        强制命中=True,
        rng=random.Random(0),
    )
    assert out["格挡"] is True
    assert out["暴击"] is False
    # 格挡免伤底 +0.40
    assert out["伤害"] == 100.0 * (1.0 - 0.40)


def test_crit_damage_multiplier():
    out = 解析伤害PVE(
        基础伤害=100.0,
        attacker={"等级": 60, "暴击效果": 1.0, "暴击伤害效果": 2.0, "精准率": 1.0},
        defender={"等级": 60, "格挡效果": 0.0, "抗暴率": 0.0},
        强制命中=True,
        rng=random.Random(0),
    )
    assert out["暴击"] is True
    assert out["伤害"] == 200.0


def test_counter_and_zone_order_in_mid():
    out = 解析伤害PVE(
        基础伤害=100.0,
        attacker={"等级": 60, "克制倍率": 1.5, "伤害乘区": 1.2},
        defender={"等级": 60},
        强制命中=True,
        禁止格挡=True,
        禁止暴击=True,
        rng=random.Random(0),
    )
    stages = out["已执行阶段"]
    assert stages.index("克制") < stages.index("格挡")
    assert stages.index("格挡") < stages.index("暴击")
    assert stages.index("暴击") < stages.index("伤害乘区")
    assert abs(out["伤害"] - 100.0 * 1.5 * 1.2) < 1e-6


def test_lifesteal_reflect_recorded():
    out = 解析伤害PVE(
        基础伤害=100.0,
        attacker={"等级": 60, "物理吸血": 0.1},
        defender={"等级": 60, "物理反伤": 0.05},
        强制命中=True,
        禁止格挡=True,
        禁止暴击=True,
        rng=random.Random(0),
    )
    assert abs(out["吸血"] - 10.0) < 1e-6
    assert abs(out["反伤"] - 5.0) < 1e-6
