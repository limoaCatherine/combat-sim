# -*- coding: utf-8 -*-
"""MMO 扩展：治疗吸收 / 无敌 / 锁1血 主路径金标。"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from 战斗模拟.管道.护盾吸收 import fifo_治疗吸收, 新建治疗吸收层
from 战斗模拟.管道.扣血 import 解析扣血PVE, 解析回血PVE
from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文

FW = Path("/workspace/combat-framework/战斗数值框架.xlsx")


def test_heal_absorb_fifo_helper():
    layers = [新建治疗吸收层(30.0), 新建治疗吸收层(20.0)]
    rem, absorbed, broken, alive = fifo_治疗吸收(layers, 45.0)
    assert absorbed == pytest.approx(45.0)
    assert rem == pytest.approx(0.0)
    assert broken == 1
    assert len(alive) == 1
    assert alive[0]["剩余容量"] == pytest.approx(5.0)

    out = 解析回血PVE(
        {
            "当前生命": 50.0,
            "生命值": 100.0,
            "治疗值": 40.0,
            "治疗吸收层": [新建治疗吸收层(25.0)],
            "守方": {"生命值": 100.0, "治疗吸收层": []},
        }
    )
    # 先吸 25，剩余 15 回血 → 生命 65
    assert out["治疗吸收量"] == pytest.approx(25.0)
    assert out["实际治疗"] == pytest.approx(15.0)
    assert out["当前生命"] == pytest.approx(65.0)
    assert out["治疗吸收层"] == []


def test_invuln_zeros_damage():
    out = 解析扣血PVE(
        {
            "当前生命": 500.0,
            "最终伤害": 200.0,
            "伤害类型": "物理",
            "状态": {"无敌"},
        }
    )
    assert out["实际扣血"] == pytest.approx(0.0)
    assert out["结算伤害"] == pytest.approx(0.0)
    assert out["已死亡"] is False


def test_lock1_hp_prevents_death():
    out = 解析扣血PVE(
        {
            "当前生命": 80.0,
            "最终伤害": 200.0,
            "伤害类型": "物理",
            "状态": {"锁1血"},
        }
    )
    assert out["当前生命"] == pytest.approx(1.0)
    assert out["实际扣血"] == pytest.approx(79.0)
    assert out["已死亡"] is False


def test_type_immune_still_primary():
    out = 解析扣血PVE(
        {
            "当前生命": 500.0,
            "最终伤害": 200.0,
            "伤害类型": "物理",
            "状态": {"免疫物理"},
        }
    )
    assert out["实际扣血"] == pytest.approx(0.0)


@pytest.fixture(scope="module")
def interpreter():
    if not FW.is_file():
        pytest.skip("框架表不在 box")
    interp = 流程解释器(工作簿路径=FW)
    if "伤害PVE" not in interp.管线名列表() or "治疗PVE" not in interp.管线名列表():
        pytest.skip("缺管线")
    return interp


def test_invuln_interpreter(interpreter):
    atk = {
        "id": "a",
        "生命": 10000.0,
        "生命上限": 10000.0,
        "伤害效果(PVE)": 1.0,
        "克制效果(PVE)": 1.0,
        "暴击伤害效果(PVE)": 1.5,
        "吸血效果(PVE)": 0.0,
        "最终增伤%": 0.0,
        "状态": set(),
        "护盾层": [],
    }
    dfd = {
        "id": "b",
        "生命": 1000.0,
        "生命上限": 1000.0,
        "闪避效果(PVE)": 0.0,
        "格挡效果(PVE)": 0.0,
        "暴击效果(PVE)": 0.0,
        "物理免伤效果(PVE)": 0.0,
        "魔法免伤效果(PVE)": 0.0,
        "格挡免伤效果(PVE)": 0.0,
        "反伤效果(PVE)": 0.0,
        "最终免伤%": 0.0,
        "状态": {"无敌"},
        "护盾层": [],
    }
    ctx = 构建上下文(
        基础伤害=300.0,
        伤害类型="物理",
        伤害来源="直接",
        攻方=atk,
        守方=dfd,
        rng=random.Random(0),
        仇恨系数=1.0,
        标记={"必中"},
    )
    ctx["命中位"] = "必中"
    result = interpreter.执行管线("伤害PVE", ctx)
    assert result.实际扣血 == pytest.approx(0.0)
    assert float(dfd["生命"]) == pytest.approx(1000.0)


def test_lock1_interpreter(interpreter):
    atk = {
        "id": "a",
        "生命": 10000.0,
        "生命上限": 10000.0,
        "伤害效果(PVE)": 1.0,
        "克制效果(PVE)": 1.0,
        "暴击伤害效果(PVE)": 1.5,
        "吸血效果(PVE)": 0.0,
        "最终增伤%": 0.0,
        "状态": set(),
        "护盾层": [],
    }
    dfd = {
        "id": "b",
        "生命": 50.0,
        "生命上限": 50.0,
        "闪避效果(PVE)": 0.0,
        "格挡效果(PVE)": 0.0,
        "暴击效果(PVE)": 0.0,
        "物理免伤效果(PVE)": 0.0,
        "魔法免伤效果(PVE)": 0.0,
        "格挡免伤效果(PVE)": 0.0,
        "反伤效果(PVE)": 0.0,
        "最终免伤%": 0.0,
        "状态": {"锁1血"},
        "护盾层": [],
    }
    ctx = 构建上下文(
        基础伤害=200.0,
        伤害类型="物理",
        伤害来源="直接",
        攻方=atk,
        守方=dfd,
        rng=random.Random(0),
        仇恨系数=1.0,
        标记={"必中"},
    )
    ctx["命中位"] = "必中"
    result = interpreter.执行管线("伤害PVE", ctx)
    assert float(dfd["生命"]) == pytest.approx(1.0)
    assert "已死亡" not in result.标记


def test_heal_absorb_interpreter(interpreter):
    atk = {
        "id": "healer",
        "生命": 1000.0,
        "生命上限": 1000.0,
        "施法治疗效果(PVE)": 1.0,
        "治疗暴击效果(PVE)": 0.0,
        "状态": set(),
        "护盾层": [],
        "治疗吸收层": [],
    }
    dfd = {
        "id": "target",
        "生命": 40.0,
        "生命上限": 100.0,
        "生命值": 100.0,
        "受治疗效果(PVE)": 1.0,
        "状态": set(),
        "护盾层": [],
        "治疗吸收层": [新建治疗吸收层(30.0)],
    }
    ctx = 构建上下文(
        基础伤害=0.0,
        伤害类型="物理",
        伤害来源="直接",
        攻方=atk,
        守方=dfd,
        rng=random.Random(0),
        仇恨系数=1.0,
        标记={"不可暴击"},
    )
    ctx["基础治疗"] = 50.0
    ctx["治疗值"] = 50.0
    ctx["暴击位"] = "不可暴击"
    result = interpreter.执行管线("治疗PVE", ctx)
    # 吸 30，回血 20 → 生命 60
    assert float(ctx.get("治疗吸收量") or 0) == pytest.approx(30.0)
    assert result.实际治疗 == pytest.approx(20.0)
    assert float(dfd["生命"]) == pytest.approx(60.0)
    assert dfd["治疗吸收层"] == []
