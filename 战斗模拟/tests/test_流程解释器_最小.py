# -*- coding: utf-8 -*-
"""流程解释器黄金路径：加载 伤害PVE，mock 面板，断言最终伤害与日志。"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from 战斗模拟.内核.战斗日志 import 战斗日志
from 战斗模拟.内核.引擎 import 战斗引擎
from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文

FW = Path("/workspace/combat-framework/战斗数值框架.xlsx")


@pytest.fixture(scope="module")
def interpreter():
    if not FW.is_file():
        pytest.skip("框架表不在 box")
    return 流程解释器(工作簿路径=FW)


def test_load_lists_pipes(interpreter):
    names = interpreter.管线名列表()
    assert "伤害PVE" in names
    assert len(names) >= 1
    # 管线名驱动：存在的都可列；驱散缺失也不炸
    cov = interpreter.opcode_coverage()
    assert cov["总步骤"] > 0
    assert cov["覆盖率%"] >= 90.0


def test_damage_pve_golden_path(interpreter):
    rng = random.Random(42)
    atk = {
        "id": "a",
        "生命": 10000.0,
        "生命上限": 10000.0,
        "伤害效果(PVE)": 1.0,
        "克制效果(PVE)": 1.0,
        "暴击伤害效果(PVE)": 1.5,
        "吸血效果(PVE)": 0.0,
        "最终增伤%": 0.0,
    }
    dfd = {
        "id": "b",
        "生命": 50000.0,
        "生命上限": 50000.0,
        "闪避效果(PVE)": 0.0,
        "格挡效果(PVE)": 0.0,
        "暴击效果(PVE)": 0.0,
        "物理免伤效果(PVE)": 0.0,
        "魔法免伤效果(PVE)": 0.0,
        "格挡免伤效果(PVE)": 0.0,
        "反伤效果(PVE)": 0.0,
        "最终免伤%": 0.0,
        "状态": set(),
        "护盾层": [],
    }
    ctx = 构建上下文(
        基础伤害=100.0,
        伤害类型="物理",
        伤害来源="直接",
        攻方=atk,
        守方=dfd,
        rng=rng,
        仇恨系数=1.0,
        标记={"必中"},
    )
    ctx["命中位"] = "必中"
    result = interpreter.执行管线("伤害PVE", ctx)
    assert result.最终伤害 >= 0.0
    assert result.步数 > 0
    assert result.最终伤害 == pytest.approx(100.0, rel=1e-6)
    # 结构化日志
    log = 战斗日志()
    log.append(
        0.0,
        "IMPACT",
        攻方id="a",
        守方id="b",
        技能或效果="测试斩击",
        结果={
            "最终伤害": result.最终伤害,
            "实际扣血": result.实际扣血,
            "标记": sorted(result.标记),
        },
    )
    assert len(log) >= 1
    assert log.export_jsonl().strip()
    assert "最终伤害" in log.export_text()


def test_mitigation_effect_defaults_to_defender():
    it = 流程解释器(管线表={})
    ctx = {
        "攻方": {"物理免伤效果(PVE)": 0.5},
        "守方": {"物理免伤效果(PVE)": 0.1},
    }
    assert it._lookup_effect("物理免伤效果(PVE)", None, ctx) == pytest.approx(0.1)
    assert it._lookup_effect("物理免伤效果(PVE)", "攻方", ctx) == pytest.approx(0.5)


def test_engine_uses_interpreter_and_log():
    if not FW.is_file():
        pytest.skip("框架表不在 box")
    eng = 战斗引擎(工作簿路径=FW, 基础伤害=120.0, 场景种子=7)
    r = eng.run_once(seed=7)
    assert r.伤害总量 >= 0.0
    assert r.日志, "战斗日志应非空"
    assert r.结算.get("最终伤害", 0) >= 0.0
    assert r.指标.get("管线") in ("伤害PVE", "伤害PVP")
