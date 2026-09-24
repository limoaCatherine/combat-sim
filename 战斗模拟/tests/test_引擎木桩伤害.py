# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from 战斗模拟.内核.引擎 import 战斗引擎
from 战斗模拟.批跑 import 跑蒙特卡洛桩
from 战斗模拟.模型.实体 import 实体

WB = Path("/workspace/combat-framework/战斗数值框架.xlsx")


def test_engine_dummy_damage_dict():
    eng = 战斗引擎(基础伤害=250.0)
    r = eng.run_once(seed=0)
    d = r.to_dict()
    assert d["伤害总量"] > 0
    assert d["指标"]["伤害总量"] == d["伤害总量"]
    assert "结算" in d
    assert d["结算"]["最终伤害"] == d["伤害总量"]


def test_engine_with_custom_entities():
    atk = 实体(id="a", 名称="攻", 等级=60, 生命=5000, 生命上限=5000, 面板={"物理穿透": 0})
    dfd = 实体(id="b", 名称="桩", 等级=60, 生命=5000, 生命上限=5000, 面板={"物理防御": 0})
    eng = 战斗引擎(攻方=atk, 守方=dfd, 基础伤害=100.0)
    r = eng.run_once(seed=1)
    assert abs(r.伤害总量 - 100.0) < 1e-6
    assert dfd.生命 == 4900.0


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_batch_returns_damage_total():
    out = 跑蒙特卡洛桩(WB, 场景名="_smoke_", 次数=3, 基础伤害=100.0)
    assert out["伤害总量"] > 0
    assert out["metrics"]["伤害总量"] == out["伤害总量"]
    assert out["metrics"]["stub"] is False
