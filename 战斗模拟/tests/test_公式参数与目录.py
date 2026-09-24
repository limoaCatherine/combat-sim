# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from 战斗模拟.load.公式参数 import 折算对抗率, 加载公式参数
from 战斗模拟.load.技能 import 加载技能目录
from 战斗模拟.load.效果 import 加载效果目录

WB = Path("/workspace/combat-framework/战斗数值框架.xlsx")


def test_opposed_rate_math():
    # X/(X+kLv+c)
    r = 折算对抗率(100, k=10, c=0, 等级=10)
    assert abs(r - 100 / (100 + 100)) < 1e-9
    assert 折算对抗率(0, 10, 5, 60) == 0.0


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_load_formula_params_has_kc():
    fp = 加载公式参数(WB)
    assert len(fp.曲线) >= 4
    assert fp.有曲线("物理免伤率")
    cur = fp.取曲线("物理免伤率")
    assert cur.k > 0 and cur.c > 0
    rate = fp.折算("物理免伤率", 1423, 60)
    assert 0.0 < rate < 1.0


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_load_skill_catalog_nonempty():
    cat = 加载技能目录(WB)
    assert len(cat) > 0
    # 抽样
    first = next(iter(cat.按编号.values()))
    assert first.编号
    assert first.仇恨系数 >= 0


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_load_effect_catalog_nonempty():
    cat = 加载效果目录(WB)
    assert len(cat) > 0
    first = next(iter(cat.按代号.values()))
    assert first.代号
