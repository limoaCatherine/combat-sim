# -*- coding: utf-8 -*-
"""光环快照冻结、层衰减、到期移除。"""
from __future__ import annotations

from 战斗模拟.内核.事件 import 事件种类
from 战斗模拟.内核.光环运行时 import (
    写入快照,
    取光环列表,
    挂载效果,
    按uid移除,
    衰减层数,
    跳动属性面板,
)
from 战斗模拟.内核.引擎 import 战斗引擎, _实体转面板
from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文
from 战斗模拟.模型.实体 import 实体


def test_快照冻结_不受攻方面板后续变化影响():
    side: dict = {"id": "t", "光环列表": []}
    ctx = {
        "效果代号": "灼烧",
        "叠加规则": "刷新",
        "快照时机": "施加时",
        "层衰减间隔": 0,
        "层衰减数量": 0,
        "驱散类型等级": "可驱散",
        "攻方": {"id": "a", "物理攻击": 100.0, "暴击": 0.2},
    }
    aura = 挂载效果(side, "灼烧", 3, 5000.0, ctx=ctx)
    写入快照(aura, ctx["攻方"], "物理攻击;暴击")
    assert aura.快照["物理攻击"] == 100.0
    assert aura.快照["暴击"] == 0.2

    ctx["攻方"]["物理攻击"] = 999.0
    panel = 跳动属性面板(aura, ctx["攻方"])
    assert panel["物理攻击"] == 100.0
    assert panel["暴击"] == 0.2

    aura.快照时机 = "每跳动"
    panel2 = 跳动属性面板(aura, ctx["攻方"])
    assert panel2["物理攻击"] == 999.0


def test_层衰减减层_耗尽移除():
    side: dict = {"id": "t", "光环列表": []}
    ctx = {
        "效果代号": "毒",
        "叠加规则": "叠层",
        "层衰减间隔": 1000,
        "层衰减数量": 2,
        "驱散类型等级": "可驱散",
    }
    aura = 挂载效果(side, "毒", 5, 10000.0, ctx=ctx)
    assert aura.层数 == 5
    inst, gone = 衰减层数(side, aura)
    assert not gone and inst is not None and inst.层数 == 3
    inst, gone = 衰减层数(side, aura)
    assert not gone and inst.层数 == 1
    inst, gone = 衰减层数(side, aura)
    assert gone and inst.层数 <= 0
    assert 取光环列表(side) == []


def test_解释器挂载与写入快照():
    interp = 流程解释器(管线表={})
    atk = {"id": "a", "法术强度": 50.0, "急速": 0.1}
    dfd = {"id": "b", "生命": 1000.0, "光环列表": []}
    ctx = 构建上下文(
        攻方=atk,
        守方=dfd,
        效果代号="寒霜",
        叠加规则="独立",
        快照时机="施加时",
        快照属性列表="法术强度;急速",
        异常层数=2,
        剩余时长=3000,
    )
    assert interp._call_func("挂载效果", "效果代号,异常层数,剩余时长", ctx) is True
    assert float(ctx["异常挂载结果"]) == 1.0
    assert len(取光环列表(dfd)) == 1
    assert interp._call_func("写入快照", "快照属性列表", ctx) is True
    aura = 取光环列表(dfd)[0]
    assert aura.快照.get("法术强度") == 50.0
    atk["法术强度"] = 1.0
    assert 跳动属性面板(aura, atk)["法术强度"] == 50.0


def test_调度存续事件_衰减与到期移除():
    atk = 实体(id="atk", 名称="攻", 生命=1000, 生命上限=1000, 等级=60)
    dfd = 实体(id="dfd", 名称="守", 生命=5000, 生命上限=5000, 等级=60)
    eng = 战斗引擎(
        攻方=atk,
        守方=dfd,
        解释器=流程解释器(管线表={}),
        加载触发表=False,
        上限毫秒=10_000,
    )
    eng.实体表[atk.id] = atk
    eng.实体表[dfd.id] = dfd
    eng.调度器.清空()

    side = _实体转面板(dfd)
    ctx = {
        "效果代号": "腐蚀",
        "叠加规则": "叠层",
        "层衰减间隔": 100.0,
        "层衰减数量": 1,
        "快照时机": "无",
        "驱散类型等级": "可驱散",
        "攻方": _实体转面板(atk),
    }
    aura = 挂载效果(side, "腐蚀", 2, 350.0, ctx=ctx)
    dfd.光环列表 = list(side["光环列表"])
    out = eng.调度光环存续(
        目标侧=side, 光环=aura, 来源id=atk.id, 目标id=dfd.id, 现在毫秒=0.0
    )
    assert out.get("衰减事件号")
    assert out.get("到期事件号")

    # 泵事件：复用 run_once 分支（通过临时扩大 time_cap 逻辑手写）
    decay_hits = 0
    for _ in range(30):
        ev = eng.调度器.推进()
        if ev is None:
            break
        kind = ev.种类
        payload = dict(ev.载荷 or {})
        now = eng.调度器.现在毫秒
        if kind in (事件种类.光环衰减.value, "AURA_DECAY"):
            decay_hits += 1
            s2 = _实体转面板(dfd)
            inst, gone = 衰减层数(
                s2,
                uid=int(payload.get("uid")),
                数量=payload.get("衰减数量"),
            )
            dfd.光环列表 = list(s2.get("光环列表") or [])
            if not gone and inst is not None:
                iv = float(payload.get("衰减间隔") or 100)
                eng.调度器.调度(
                    now + iv,
                    事件种类.光环衰减.value,
                    {**payload, "uid": inst.uid},
                )
        elif kind in (事件种类.光环到期.value, "AURA_EXPIRE"):
            s2 = _实体转面板(dfd)
            uid = payload.get("uid")
            if uid is not None:
                按uid移除(s2, int(uid))
            else:
                from 战斗模拟.内核.光环运行时 import 移除同效果

                移除同效果(s2, str(payload.get("效果代号") or ""))
            dfd.光环列表 = list(s2.get("光环列表") or [])

    assert decay_hits >= 1
    assert len(dfd.光环列表) == 0
