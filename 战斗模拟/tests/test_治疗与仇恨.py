# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from 战斗模拟.管道.治疗 import 解析治疗PVE
from 战斗模拟.管道.仇恨 import 解析伤害仇恨PVE, 伤害仇恨系数, 治疗仇恨系数
from 公共.错误 import 数据缺失错误


def test_heal_bonus_pct():
    out = 解析治疗PVE(基础治疗=100.0, healer={"治疗效果%": 0.2})
    assert abs(out["原始治疗"] - 120.0) < 1e-6
    assert out["治疗"] == 120.0


def test_heal_overheal_cap():
    out = 解析治疗PVE(
        基础治疗=100.0,
        healer={"治疗效果%": 0.0},
        target={"生命": 950.0, "生命上限": 1000.0},
    )
    assert out["治疗"] == 50.0
    assert out["过量治疗"] == 50.0


def test_heal_crit_expected():
    out = 解析治疗PVE(
        基础治疗=100.0,
        healer={"治疗效果%": 0.0, "暴击效果": 0.5, "暴击伤害效果": 2.0},
        可暴击=True,
        期望模式=True,
    )
    # 100 * ((1-0.5)+0.5*2) = 150
    assert abs(out["原始治疗"] - 150.0) < 1e-6


def test_threat_formula():
    assert 伤害仇恨系数 == 1.0
    assert 治疗仇恨系数 == 0.05
    out = 解析伤害仇恨PVE(伤害=1000.0, 治疗=200.0, 技能仇恨系数=2.0)
    # (1000*1 + 200*0.05)*2 = 2020
    assert abs(out["仇恨"] - 2020.0) < 1e-6


def test_threat_negative_coef_raises():
    with pytest.raises(数据缺失错误):
        解析伤害仇恨PVE(伤害=10, 技能仇恨系数=-1)
