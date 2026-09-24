# -*- coding: utf-8 -*-
"""Phase F 金标：fixture 驱动伤害PVE + proc ICD。"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文
from 战斗模拟.内核.触发调度 import 触发定义, 触发调度器
from 战斗模拟.内核.事件 import 事件调度器
from 战斗模拟.内核.战斗日志 import 战斗日志

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
DUMMY_FIXTURE = GOLDEN_DIR / "木桩_直伤命中.json"
PROC_FIXTURE = GOLDEN_DIR / "proc_ICD.json"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _resolve_workbook(candidates: list[str]) -> Path:
    for raw in candidates:
        p = Path(raw)
        if p.is_file():
            return p
    pytest.skip(f"无可用工作簿: {candidates}")


@pytest.fixture(scope="module")
def dummy_fx() -> dict:
    if not DUMMY_FIXTURE.is_file():
        pytest.skip("缺少木桩_直伤命中.json")
    return _load_json(DUMMY_FIXTURE)


@pytest.fixture(scope="module")
def interpreter(dummy_fx: dict) -> 流程解释器:
    wb = _resolve_workbook(dummy_fx.get("workbook_candidates") or [])
    interp = 流程解释器(工作簿路径=wb)
    names = interp.管线名列表()
    if "伤害PVE" not in names:
        # 32-sheet 损坏时回退其它候选
        for raw in dummy_fx.get("workbook_candidates") or []:
            p = Path(raw)
            if not p.is_file() or p == wb:
                continue
            alt = 流程解释器(工作簿路径=p)
            if "伤害PVE" in alt.管线名列表():
                return alt
        pytest.skip("工作簿缺少 伤害PVE 管线")
    return interp


def test_golden_fixtures_exist():
    assert DUMMY_FIXTURE.is_file()
    assert PROC_FIXTURE.is_file()


def test_木桩_直伤命中_期望模式(interpreter: 流程解释器, dummy_fx: dict):
    inp = dict(dummy_fx["input"])
    expect = dummy_fx["expect"]
    seed = int(dummy_fx.get("seed") or 42)
    rng = random.Random(seed)

    标记 = set(inp.pop("标记") or [])
    命中位 = inp.pop("命中位", None)
    期望模式 = bool(inp.pop("期望模式", True))
    攻方 = dict(inp.pop("攻方"))
    守方 = dict(inp.pop("守方"))
    # JSON 用 list；解释器要 set
    if isinstance(守方.get("状态"), list):
        守方["状态"] = set(守方["状态"])

    ctx = 构建上下文(
        基础伤害=float(inp.get("基础伤害") or 0),
        伤害类型=str(inp.get("伤害类型") or "物理"),
        伤害来源=str(inp.get("伤害来源") or "直接"),
        攻方=攻方,
        守方=守方,
        rng=rng,
        仇恨系数=float(inp.get("仇恨系数") or 1.0),
        标记=标记,
        期望模式=期望模式,
    )
    if 命中位 is not None:
        ctx["命中位"] = 命中位

    pipe = str(dummy_fx.get("pipe") or "伤害PVE")
    result = interpreter.执行管线(pipe, ctx)

    assert result.最终伤害 >= float(expect.get("最终伤害_min", 0.0))
    assert result.步数 >= int(expect.get("步数_min", 1))

    if "最终伤害" in expect:
        rel = float(expect.get("最终伤害_rel") or 1e-6)
        assert result.最终伤害 == pytest.approx(float(expect["最终伤害"]), rel=rel)

    if expect.get("assert_not_dodged"):
        flags = {str(x) for x in (result.标记 or set())}
        for bad in expect.get("forbidden_flags") or ["已闪避", "闪避", "dodged"]:
            assert bad not in flags, f"强制命中路径不应含 {bad}: {flags}"
        # 上下文命中位也应非闪避
        hit = str(result.上下文.get("命中位") or ctx.get("命中位") or "")
        assert hit in ("", "必中", "命中", "暴击", "格挡") or "闪" not in hit


def test_木桩_直伤命中_seeded_rng(interpreter: 流程解释器, dummy_fx: dict):
    """同一 fixture：关闭期望模式、固定 seed，强制命中仍应稳定。"""
    inp = dict(dummy_fx["input"])
    expect = dummy_fx["expect"]
    seed = int(dummy_fx.get("seed") or 42)
    rng = random.Random(seed)

    标记 = set(inp.get("标记") or []) | {"必中"}
    攻方 = dict(inp["攻方"])
    守方 = dict(inp["守方"])
    if isinstance(守方.get("状态"), list):
        守方["状态"] = set(守方["状态"])

    ctx = 构建上下文(
        基础伤害=float(inp["基础伤害"]),
        伤害类型=str(inp.get("伤害类型") or "物理"),
        伤害来源=str(inp.get("伤害来源") or "直接"),
        攻方=攻方,
        守方=守方,
        rng=rng,
        仇恨系数=float(inp.get("仇恨系数") or 1.0),
        标记=标记,
        期望模式=False,
    )
    ctx["命中位"] = inp.get("命中位") or "必中"

    result = interpreter.执行管线(str(dummy_fx.get("pipe") or "伤害PVE"), ctx)
    assert result.最终伤害 >= 0.0
    # 无乘区时直伤应≈基础；允许极小浮点差
    if "最终伤害" in expect:
        assert result.最终伤害 == pytest.approx(float(expect["最终伤害"]), rel=1e-6)
    flags = {str(x) for x in (result.标记 or set())}
    assert "已闪避" not in flags and "闪避" not in flags


def test_proc_ICD_from_fixture():
    fx = _load_json(PROC_FIXTURE)
    assert fx.get("kind") == "proc_icd"
    t = fx["trigger"]
    d = 触发定义(
        效果代号=t["效果代号"],
        结算时机=t["结算时机"],
        触发概率百分=float(t["触发概率百分"]),
        结算内置冷却=float(t["结算内置冷却"]),
        额外动作=list(t.get("额外动作") or []),
    )
    disp = 触发调度器(
        [d],
        rng=random.Random(int(fx.get("seed") or 1)),
        调度器=事件调度器(),
        日志=战斗日志(),
    )
    for step in fx["timeline"]:
        r = disp.尝试触发(
            d,
            现在毫秒=float(step["t_ms"]),
            来源id="a",
            目标id="b",
        )
        assert r.成功 is bool(step["expect_success"]), step
        if step.get("reason"):
            assert r.原因 == step["reason"]

    exp = fx["expect"]
    assert disp.成功次数 == int(exp["成功次数"])
    assert disp.冷却拦截次数 == int(exp["冷却拦截次数"])
