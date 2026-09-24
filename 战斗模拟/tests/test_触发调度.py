# -*- coding: utf-8 -*-
"""触发调度：ICD / 概率 / 暴击钩子。"""
from __future__ import annotations

import random

from 战斗模拟.内核.事件 import 事件调度器, 事件种类
from 战斗模拟.内核.战斗日志 import 战斗日志
from 战斗模拟.内核.触发调度 import 触发定义, 触发调度器


def _disp(defs, *, rng=None, sch=None, log=None) -> 触发调度器:
    return 触发调度器(
        defs,
        rng=rng,
        调度器=sch or 事件调度器(),
        日志=log or 战斗日志(),
    )


def test_icd_blocks_second_proc_within_window():
    d = 触发定义(
        效果代号="测试爆炎",
        结算时机="命中时",
        触发概率百分=100.0,
        结算内置冷却=1000.0,
        额外动作=["伤害(50)"],
    )
    disp = _disp([d], rng=random.Random(1))
    r1 = disp.尝试触发(d, 现在毫秒=0.0, 来源id="a", 目标id="b")
    assert r1.成功 is True
    r2 = disp.尝试触发(d, 现在毫秒=500.0, 来源id="a", 目标id="b")
    assert r2.成功 is False
    assert r2.原因 == "ICD"
    assert disp.冷却拦截次数 == 1
    r3 = disp.尝试触发(d, 现在毫秒=1000.0, 来源id="a", 目标id="b")
    assert r3.成功 is True
    assert disp.成功次数 == 2


def test_probability_100_always_0_never():
    always = 触发定义(
        效果代号="必触发",
        结算时机="命中时",
        触发概率百分=100.0,
    )
    never = 触发定义(
        效果代号="从不触发",
        结算时机="命中时",
        触发概率百分=0.0,
    )
    rng = random.Random(0)
    disp = _disp([always, never], rng=rng)
    for _ in range(20):
        assert disp.尝试触发(
            always, 现在毫秒=0.0, 来源id="a", 目标id="b", 入队=False
        ).成功
    fails = [
        disp.尝试触发(never, 现在毫秒=0.0, 来源id="a", 目标id="b", 入队=False)
        for _ in range(20)
    ]
    assert all(not r.成功 for r in fails)
    assert all(r.原因 == "概率未中" for r in fails)


def test_crit_hook_only_when_marked_crit():
    d = 触发定义(
        效果代号="暴击回响",
        结算时机="暴击时",
        触发概率百分=100.0,
        额外动作=["伤害(10)"],
    )
    sch = 事件调度器()
    disp = _disp([d], rng=random.Random(2), sch=sch)

    # 非暴击上下文：处理「命中时」不应触发暴击订阅
    hit_only = disp.处理钩子(
        "命中时",
        现在毫秒=0.0,
        来源id="a",
        目标id="b",
        上下文={"暴击": False, "标记": set()},
    )
    assert hit_only == []  # 无命中时订阅
    assert disp.成功次数 == 0

    # 显式暴击钩子
    crits = disp.处理钩子(
        "暴击时",
        现在毫秒=0.0,
        来源id="a",
        目标id="b",
        上下文={"暴击": True, "标记": {"已暴击"}},
    )
    assert len(crits) == 1 and crits[0].成功
    # 应入队 PROC
    kinds = []
    while True:
        ev = sch.推进()
        if ev is None:
            break
        kinds.append(ev.种类)
    assert 事件种类.触发.value in kinds


def test_engine_crit_hook_wiring():
    """引擎：仅当 hit 标记已暴击时调用暴击时钩子。"""
    from 战斗模拟.内核.引擎 import 战斗引擎
    from 战斗模拟.模型.实体 import 实体

    d_hit = 触发定义(效果代号="命中计数", 结算时机="命中时", 触发概率百分=100.0)
    d_crit = 触发定义(效果代号="暴击计数", 结算时机="暴击时", 触发概率百分=100.0)
    disp = 触发调度器([d_hit, d_crit], rng=random.Random(3))

    eng = 战斗引擎(
        触发=disp,
        加载触发表=False,
        解释器=__import__("战斗模拟.内核.流程解释器", fromlist=["流程解释器"]).流程解释器(
            管线表={}
        ),
        攻方=实体(id="a", 名称="a", 阵营="友方", 生命=1000, 生命上限=1000, 等级=60),
        守方=实体(id="b", 名称="b", 阵营="敌方", 生命=10000, 生命上限=10000, 等级=60),
        基础伤害=50.0,
    )
    # 非暴击
    eng._伤害后触发钩子(
        atk=eng.攻方,
        dfd=eng.守方,
        hit={"命中": True, "暴击": False, "标记": []},
        now=0.0,
    )
    assert disp.成功次数 == 1  # 仅命中时（受击时无订阅；攻击时无订阅）
    # 再打一次暴击
    before = disp.成功次数
    eng._伤害后触发钩子(
        atk=eng.攻方,
        dfd=eng.守方,
        hit={"命中": True, "暴击": True, "标记": ["已暴击"]},
        now=10.0,
    )
    # 命中时 + 暴击时
    assert disp.成功次数 == before + 2


def test_parse_extra_action_and_schedule_pipe_request():
    from 战斗模拟.内核.触发调度 import 解析额外动作

    assert 解析额外动作("伤害(100)").get("管线族") == "伤害"
    assert 解析额外动作("治疗(50)").get("管线族") == "治疗"
    assert 解析额外动作("施加(失衡)").get("管线族") == "效果事件"
    assert 解析额外动作("驱散(魔法,2)").get("管线族") == "驱散"

    d = 触发定义(
        效果代号="附伤",
        结算时机="命中时",
        触发概率百分=100.0,
        额外动作=["伤害(30)", "施加(失衡)"],
    )
    sch = 事件调度器()
    disp = _disp([d], rng=random.Random(4), sch=sch)
    r = disp.尝试触发(d, 现在毫秒=5.0, 来源id="a", 目标id="b")
    assert r.成功
    assert len(r.管线请求) == 2
    kinds = []
    payloads = []
    while True:
        ev = sch.推进()
        if ev is None:
            break
        kinds.append(ev.种类)
        payloads.append(ev.载荷)
    assert 事件种类.触发.value in kinds
    assert 事件种类.命中.value in kinds  # 伤害请求
    assert 事件种类.光环施加.value in kinds  # 施加请求
