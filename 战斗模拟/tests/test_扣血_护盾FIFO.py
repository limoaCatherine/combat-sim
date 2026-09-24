# -*- coding: utf-8 -*-
"""扣血 / 护盾 FIFO 核心金标 — UGit 容量 FIFO + 类型过滤。

次数盾 / 过量转盾 / 治疗吸收 / 无敌 / 锁1血 见 test_护盾进阶.py、test_治疗吸收_无敌锁血.py。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from 战斗模拟.管道.扣血 import 解析扣血PVE
from 战斗模拟.管道.护盾吸收 import (
    fifo_护盾吸收,
    护盾类型可吸收,
    护盾剩余容量,
    护盾仍存活,
    是穿透护盾的伤害,
)
from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
FW = Path("/workspace/combat-framework/战斗数值框架.xlsx")


def _load(name: str) -> dict:
    with (GOLDEN_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def _mk_shield(*, absorb_type: str = "全伤害", capacity: float = 0.0) -> dict:
    c = float(capacity)
    return {
        "absorb_type": absorb_type,
        "护盾吸收类型": absorb_type,
        "remaining_capacity": c,
        "capacity": c,
        "剩余容量": c,
        "剩余": c,
        "hits_only": False,
        "hit_capped": False,
        "remaining_hits": 0,
    }


@pytest.fixture(scope="module")
def interpreter():
    if not FW.is_file():
        pytest.skip("框架表不在 box")
    interp = 流程解释器(工作簿路径=FW)
    if "伤害PVE" not in interp.管线名列表():
        pytest.skip("无伤害PVE管线")
    return interp


def _run_dmg(
    interpreter,
    *,
    base,
    dtype="物理",
    hp_dfd=1000.0,
    dfd_shields=None,
    atk_shields=None,
    dfd_states=None,
    reflect=0.0,
    hp_atk=10000.0,
):
    atk = {
        "id": "a",
        "生命": float(hp_atk),
        "生命上限": float(hp_atk),
        "伤害效果(PVE)": 1.0,
        "克制效果(PVE)": 1.0,
        "暴击伤害效果(PVE)": 1.5,
        "吸血效果(PVE)": 0.0,
        "最终增伤%": 0.0,
        "状态": set(),
        "护盾层": list(atk_shields or []),
    }
    dfd = {
        "id": "b",
        "生命": float(hp_dfd),
        "生命上限": float(hp_dfd),
        "闪避效果(PVE)": 0.0,
        "格挡效果(PVE)": 0.0,
        "暴击效果(PVE)": 0.0,
        "物理免伤效果(PVE)": 0.0,
        "魔法免伤效果(PVE)": 0.0,
        "格挡免伤效果(PVE)": 0.0,
        "反伤效果(PVE)": float(reflect),
        "最终免伤%": 0.0,
        "状态": set(dfd_states or []),
        "护盾层": list(dfd_shields or []),
    }
    ctx = 构建上下文(
        基础伤害=float(base),
        伤害类型=dtype,
        伤害来源="直接",
        攻方=atk,
        守方=dfd,
        rng=random.Random(0),
        仇恨系数=1.0,
        标记={"必中"},
    )
    ctx["命中位"] = "必中"
    result = interpreter.执行管线("伤害PVE", ctx)
    return result, ctx, atk, dfd


def test_core_absorb_types_ugit():
    """全伤害=物+魔。"""
    assert 护盾类型可吸收(_mk_shield(absorb_type="全伤害"), "物理") is True
    assert 护盾类型可吸收(_mk_shield(absorb_type="全伤害"), "魔法") is True
    assert 是穿透护盾的伤害("物理") is False
    assert 是穿透护盾的伤害("魔法") is False
    assert 护盾类型可吸收(_mk_shield(absorb_type="仅物理"), "魔法") is False
    assert 护盾类型可吸收(_mk_shield(absorb_type="仅魔法"), "魔法") is True
    assert 护盾类型可吸收(_mk_shield(absorb_type="无"), "物理") is False


def test_physical_hits_full_shield():
    shields = [_mk_shield(absorb_type="全伤害", capacity=500.0)]
    rem, absorbed, broken, alive = fifo_护盾吸收(shields, 300.0, "物理")
    assert absorbed == pytest.approx(300.0)
    assert rem == pytest.approx(0.0)


def test_fifo_capacity_order_and_type_filter():
    """FIFO：先入先吸；类型不匹配跳过保留。"""
    s_phys = _mk_shield(absorb_type="仅物理", capacity=40.0)
    s_all = _mk_shield(absorb_type="全伤害", capacity=30.0)
    rem, absorbed, broken, alive = fifo_护盾吸收([s_phys, s_all], 50.0, "魔法")
    # 物盾跳过，全伤害吸 30，穿透 20
    assert absorbed == pytest.approx(30.0)
    assert rem == pytest.approx(20.0)
    assert broken == 1
    assert len(alive) == 1
    assert alive[0]["absorb_type"] == "仅物理"
    assert 护盾仍存活(alive[0])


def test_1_无盾扣血夹断死亡(interpreter):
    fx = _load("扣血_无盾过量死亡.json")
    out = 解析扣血PVE(fx["input"])
    assert out["实际扣血"] == pytest.approx(150.0)
    assert out["过量伤害"] == pytest.approx(50.0)
    assert out["已死亡"] is True
    result, ctx, atk, dfd = _run_dmg(interpreter, base=200.0, hp_dfd=150.0)
    assert result.实际扣血 == pytest.approx(150.0)
    assert float(ctx["过量伤害"]) == pytest.approx(50.0)
    assert "已死亡" in result.标记
    assert float(dfd["生命"]) == pytest.approx(0.0)


def test_2_一层全伤害盾吸收破盾(interpreter):
    fx = _load("扣血_单层全伤害破盾.json")
    out = 解析扣血PVE(fx["input"])
    assert out["护盾吸收量"] == pytest.approx(80.0)
    assert out["实际扣血"] == pytest.approx(20.0)
    assert out["本次破盾数"] == 1

    sh = _mk_shield(absorb_type="全伤害", capacity=80.0)
    result, ctx, atk, dfd = _run_dmg(
        interpreter, base=100.0, hp_dfd=100.0, dfd_shields=[sh]
    )
    assert float(ctx["护盾吸收量"]) == pytest.approx(80.0)
    assert result.实际扣血 == pytest.approx(20.0)
    assert "已破盾" in result.标记
    assert float(dfd["生命"]) == pytest.approx(80.0)
    assert len(dfd["护盾层"]) == 0


def test_3_仅物理盾对魔法不吸收(interpreter):
    fx = _load("扣血_仅物理盾无视魔法.json")
    out = 解析扣血PVE(fx["input"])
    assert out["护盾吸收量"] == pytest.approx(0.0)
    assert out["实际扣血"] == pytest.approx(100.0)

    sh = _mk_shield(absorb_type="仅物理", capacity=500.0)
    result, ctx, atk, dfd = _run_dmg(
        interpreter, base=100.0, dtype="魔法", hp_dfd=200.0, dfd_shields=[sh]
    )
    assert float(ctx["护盾吸收量"]) == pytest.approx(0.0)
    assert result.实际扣血 == pytest.approx(100.0)
    assert len(dfd["护盾层"]) == 1
    assert 护盾仍存活(dfd["护盾层"][0])


def test_4_物魔免疫_ugit主路径(interpreter):
    """UGit：免疫物理 / 免疫魔法 清零结算，不耗盾。"""
    sh = _mk_shield(absorb_type="全伤害", capacity=80.0)
    out = 解析扣血PVE(
        {
            "当前生命": 150.0,
            "最终伤害": 100.0,
            "伤害类型": "物理",
            "状态": {"免疫物理"},
            "护盾层": [dict(sh)],
        }
    )
    assert out["结算伤害"] == 0.0
    assert out["实际扣血"] == 0.0
    assert out["护盾吸收量"] == 0.0

    result, ctx, atk, dfd = _run_dmg(
        interpreter,
        base=100.0,
        hp_dfd=150.0,
        dfd_shields=[_mk_shield(absorb_type="全伤害", capacity=80.0)],
        dfd_states={"免疫物理"},
    )
    assert result.实际扣血 == pytest.approx(0.0)
    assert float(dfd["生命"]) == pytest.approx(150.0)
    assert 护盾剩余容量(dfd["护盾层"][0]) == pytest.approx(80.0)
    assert "已死亡" not in result.标记

    # 免疫魔法不挡物理
    out2 = 解析扣血PVE(
        {
            "当前生命": 150.0,
            "最终伤害": 40.0,
            "伤害类型": "物理",
            "状态": {"免疫魔法"},
            "护盾层": [],
        }
    )
    assert out2["实际扣血"] == pytest.approx(40.0)


def test_4b_无敌_设计扩展(interpreter):
    """设计扩展：泛无敌仍清零（非 UGit 必经）。"""
    fx = _load("扣血_无敌.json")
    out = 解析扣血PVE(fx["input"])
    assert out["结算伤害"] == 0.0
    assert out["实际扣血"] == 0.0

    sh = _mk_shield(absorb_type="全伤害", capacity=80.0)
    result, ctx, atk, dfd = _run_dmg(
        interpreter, base=100.0, hp_dfd=150.0, dfd_shields=[sh], dfd_states={"无敌"}
    )
    assert result.实际扣血 == pytest.approx(0.0)
    assert float(dfd["生命"]) == pytest.approx(150.0)
    assert 护盾剩余容量(dfd["护盾层"][0]) == pytest.approx(80.0)
    assert "已死亡" not in result.标记


def test_5_反伤打攻方换结算目标(interpreter):
    fx = _load("扣血_反伤攻方盾.json")
    dfd_sh = [_mk_shield(**s) for s in fx["input"]["守方护盾"]]
    atk_sh = [_mk_shield(**s) for s in fx["input"]["攻方护盾"]]
    result, ctx, atk, dfd = _run_dmg(
        interpreter,
        base=fx["input"]["基础伤害"],
        hp_dfd=fx["input"]["守方生命"],
        hp_atk=fx["input"]["攻方生命"],
        dfd_shields=dfd_sh,
        atk_shields=atk_sh,
        reflect=fx["input"]["反伤效果"],
    )
    exp = fx["expect"]
    assert result.实际扣血 == pytest.approx(exp["实际扣血"])
    assert float(dfd["生命"]) == pytest.approx(exp["守方生命"])
    assert float(ctx.get("实际反伤扣血") or 0.0) == pytest.approx(exp["实际反伤扣血"])
    assert float(atk["生命"]) == pytest.approx(exp["攻方生命"])
    assert len(atk["护盾层"]) == exp["攻方存活护盾数"]
    assert len(dfd["护盾层"]) == exp["守方存活护盾数"]
