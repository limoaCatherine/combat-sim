# -*- coding: utf-8 -*-
from __future__ import annotations

from 战斗模拟.内核.事件 import KIND_IMPACT, KIND_TICK, 事件调度器


def test_schedule_advance_order():
    sch = 事件调度器()
    id_late = sch.调度(200.0, KIND_IMPACT, {"x": 2})
    id_early = sch.调度(50.0, KIND_TICK, {"x": 1})
    del id_late, id_early
    e1 = sch.推进()
    assert e1 is not None and e1.种类 == KIND_TICK and e1.时间毫秒 == 50.0
    assert sch.现在毫秒 == 50.0
    e2 = sch.推进()
    assert e2 is not None and e2.种类 == KIND_IMPACT and e2.时间毫秒 == 200.0


def test_cancel():
    sch = 事件调度器()
    a = sch.调度(10.0, KIND_TICK, {})
    b = sch.调度(20.0, KIND_IMPACT, {})
    assert sch.取消(a) is True
    assert sch.取消(a) is False
    ev = sch.推进()
    assert ev is not None and ev.序号 == b
    assert sch.推进() is None


def test_queue_len_ignores_cancelled():
    sch = 事件调度器()
    a = sch.调度(1.0, KIND_TICK, {})
    sch.调度(2.0, KIND_TICK, {})
    sch.取消(a)
    assert sch.队列长度 == 1
