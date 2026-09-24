# -*- coding: utf-8 -*-
"""事件调度器：种类扩展 + cancel_by_predicate。"""
from __future__ import annotations

from 战斗模拟.内核.事件 import (
    KIND_DOT_TICK,
    KIND_IMPACT,
    KIND_TICK,
    事件种类,
    事件调度器,
)


def test_kinds_cover_simc_set():
    required = {
        "心跳",
        "GCD就绪",
        "施法开始",
        "施法完成",
        "引导跳",
        "命中",
        "持续伤害跳",
        "持续治疗跳",
        "光环施加",
        "光环刷新",
        "光环叠层",
        "光环到期",
        "光环衰减",
        "触发",
        "驱散",
        "护盾破碎",
        "死亡",
        "时间轴",
        "移动",
        "自定义",
    }
    names = {m.name for m in 事件种类}
    assert required <= names
    assert KIND_TICK == 事件种类.心跳.value
    assert KIND_IMPACT == 事件种类.命中.value
    assert KIND_DOT_TICK == 事件种类.持续伤害跳.value


def test_cancel_by_predicate():
    sch = 事件调度器()
    sch.调度(10.0, KIND_TICK, {"a": 1})
    sch.调度(20.0, KIND_IMPACT, {"a": 2})
    sch.调度(30.0, KIND_DOT_TICK, {"a": 3})
    n = sch.按条件取消(lambda e: e.种类 == KIND_IMPACT)
    assert n == 1
    assert sch.队列长度 == 2
    e1 = sch.推进()
    assert e1 is not None and e1.种类 == KIND_TICK
    e2 = sch.推进()
    assert e2 is not None and e2.种类 == KIND_DOT_TICK
    assert sch.推进() is None


def test_english_alias_cancel_by_predicate():
    sch = 事件调度器()
    sch.schedule(5.0, KIND_TICK, {})
    sch.schedule(15.0, KIND_IMPACT, {})
    assert sch.cancel_by_predicate(lambda e: e.kind == KIND_TICK) == 1
    ev = sch.advance()
    assert ev is not None and ev.kind == KIND_IMPACT
