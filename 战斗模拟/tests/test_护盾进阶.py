# -*- coding: utf-8 -*-
"""护盾进阶主路径：次数盾 hits_only / hit_capped + 过量转盾（UGit底 + MMO扩展）。"""
from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from 战斗模拟.管道.护盾吸收 import (
    fifo_护盾吸收,
    护盾仍存活,
    护盾剩余容量,
    扣减护盾层,
    新建容量盾,
    执行过量转盾,
    是次数盾,
    是次数容量盾,
)
from 战斗模拟.管道.扣血 import 解析扣血PVE, 解析回血PVE
from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文

FW = Path("/workspace/combat-framework/战斗数值框架.xlsx")


def _hits_only_shield(*, hits: int = 1, absorb_type: str = "全伤害") -> dict:
    return 新建容量盾(
        0.0,
        吸收类型=absorb_type,
        remaining_hits=hits,
        hits_only=True,
    )


def _hit_capped_shield(
    *, capacity: float, hits: int = 1, absorb_type: str = "全伤害"
) -> dict:
    return 新建容量盾(
        capacity,
        吸收类型=absorb_type,
        remaining_hits=hits,
        hit_capped=True,
    )


def test_hits_only_infer_from_hits_gt_zero():
    """护盾次数>0 且容量≈0 → 推断 hits_only。"""
    sh = 新建容量盾(0.0, remaining_hits=2)
    assert 是次数盾(sh)
    assert not 是次数容量盾(sh)


def test_hit_capped_infer_from_hits_and_capacity():
    """护盾次数>0 且容量>0 → 推断 hit_capped。"""
    sh = 新建容量盾(80.0, remaining_hits=3)
    assert 是次数容量盾(sh)
    assert not 是次数盾(sh)


def test_hits_only_blocks_full_hit_then_gone():
    sh = _hits_only_shield(hits=1)
    assert 是次数盾(sh)
    assert 护盾仍存活(sh)
    assert 护盾剩余容量(sh) == math.inf

    rem, absorbed, broken, alive = fifo_护盾吸收([sh], 999.0, "物理")
    assert rem == pytest.approx(0.0)
    assert absorbed == pytest.approx(999.0)
    assert broken == 1
    assert alive == []
    assert not 护盾仍存活(sh)

    sh2 = _hits_only_shield(hits=1)
    out = 解析扣血PVE(
        {
            "当前生命": 500.0,
            "最终伤害": 999.0,
            "伤害类型": "物理",
            "护盾层": [sh2],
        }
    )
    assert out["护盾吸收量"] == pytest.approx(999.0)
    assert out["实际扣血"] == pytest.approx(0.0)
    assert out["本次破盾数"] == 1
    assert out["护盾层"] == []


def test_hit_capped_needs_hits_and_capacity():
    sh = _hit_capped_shield(capacity=50.0, hits=1)
    rem, absorbed, broken, alive = fifo_护盾吸收([sh], 100.0, "物理")
    assert absorbed == pytest.approx(50.0)
    assert rem == pytest.approx(50.0)
    assert broken == 1
    assert alive == []

    sh2 = _hit_capped_shield(capacity=100.0, hits=1)
    overflow = 扣减护盾层(sh2, 30.0)
    assert overflow == pytest.approx(0.0)
    assert sh2["剩余容量"] == pytest.approx(70.0)
    assert sh2["remaining_hits"] == 0
    assert not 护盾仍存活(sh2)

    sh3 = _hit_capped_shield(capacity=40.0, hits=2)
    rem, absorbed, broken, alive = fifo_护盾吸收([sh3], 40.0, "魔法")
    assert absorbed == pytest.approx(40.0)
    assert rem == pytest.approx(0.0)
    assert broken == 1

    out = 解析扣血PVE(
        {
            "当前生命": 200.0,
            "最终伤害": 80.0,
            "伤害类型": "物理",
            "护盾层": [_hit_capped_shield(capacity=50.0, hits=1)],
        }
    )
    assert out["护盾吸收量"] == pytest.approx(50.0)
    assert out["实际扣血"] == pytest.approx(30.0)
    assert out["本次破盾数"] == 1


def test_overheal_to_shield_via_helper():
    ctx = {
        "当前生命": 100.0,
        "治疗值": 40.0,
        "生命值": 100.0,
        "标记": {"过量转盾开启"},
        "结算目标": "守方",
        "守方": {"生命": 100.0, "生命上限": 100.0, "护盾层": []},
        "护盾层": [],
    }
    ctx["护盾层"] = ctx["守方"]["护盾层"]
    out = 解析回血PVE(ctx)
    assert out["实际治疗"] == pytest.approx(0.0)
    assert out["过量治疗"] == pytest.approx(40.0)
    assert out["过量转盾量"] == pytest.approx(40.0)
    assert len(out["护盾层"]) == 1
    sh = out["护盾层"][0]
    assert sh["吸收类型"] == "全伤害" or sh["护盾吸收类型"] == "全伤害"
    assert sh["剩余容量"] == pytest.approx(40.0)

    out2 = 解析回血PVE(
        {"当前生命": 100.0, "治疗值": 40.0, "生命值": 100.0, "护盾层": []}
    )
    assert out2["过量转盾量"] == pytest.approx(0.0)
    assert out2["护盾层"] == []


def test_执行过量转盾_direct():
    layers: list = []
    side = {"护盾层": layers}
    ctx = {
        "标记": {"过量转盾开启"},
        "过量转盾量": 25.0,
        "结算目标": "守方",
        "守方": side,
        "护盾层": layers,
    }
    got = 执行过量转盾(ctx)
    assert got == pytest.approx(25.0)
    assert len(layers) == 1
    assert layers[0]["剩余容量"] == pytest.approx(25.0)


@pytest.fixture(scope="module")
def interpreter():
    if not FW.is_file():
        pytest.skip("框架表不在 box")
    interp = 流程解释器(工作簿路径=FW)
    pipes = interp.管线名列表()
    if "治疗PVE" not in pipes and "回血PVE" not in pipes and "伤害PVE" not in pipes:
        pytest.skip("无相关管线")
    return interp


def test_overheal_to_shield_interpreter(interpreter):
    pipes = interpreter.管线名列表()
    atk = {
        "id": "healer",
        "生命": 1000.0,
        "生命上限": 1000.0,
        "施法治疗效果(PVE)": 1.0,
        "治疗暴击效果(PVE)": 0.0,
        "状态": set(),
        "护盾层": [],
    }
    dfd = {
        "id": "target",
        "生命": 100.0,
        "生命上限": 100.0,
        "生命值": 100.0,
        "受治疗效果(PVE)": 1.0,
        "状态": set(),
        "护盾层": [],
    }
    if "治疗PVE" in pipes:
        ctx = 构建上下文(
            基础伤害=0.0,
            伤害类型="物理",
            伤害来源="直接",
            攻方=atk,
            守方=dfd,
            rng=random.Random(0),
            仇恨系数=1.0,
            标记={"过量转盾开启", "不可暴击"},
        )
        ctx["基础治疗"] = 40.0
        ctx["治疗值"] = 40.0
        ctx["暴击位"] = "不可暴击"
        interpreter.执行管线("治疗PVE", ctx)
        assert float(ctx.get("溢出治疗") or 0) == pytest.approx(40.0)
        assert float(ctx.get("过量转盾量") or 0) == pytest.approx(40.0)
        assert len(dfd["护盾层"]) == 1
        assert float(dfd["护盾层"][-1].get("剩余容量") or 0) == pytest.approx(40.0)
        return

    ctx = {
        "标记": {"过量转盾开启"},
        "溢出治疗": 40.0,
        "结算目标": "守方",
        "守方": dfd,
        "护盾层": dfd["护盾层"],
        "过量转盾量": 0.0,
    }
    interpreter._do_set("设过量转盾量", "溢出治疗", ctx)  # noqa: SLF001
    assert float(ctx["过量转盾量"]) == pytest.approx(40.0)
    assert len(dfd["护盾层"]) == 1


def test_hits_only_interpreter_damage(interpreter):
    if "伤害PVE" not in interpreter.管线名列表():
        pytest.skip("无伤害PVE")
    sh = _hits_only_shield(hits=1)
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
        "状态": set(),
        "护盾层": [sh],
    }
    ctx = 构建上下文(
        基础伤害=999.0,
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
    assert len(dfd["护盾层"]) == 0
