# -*- coding: utf-8 -*-
"""驱散移除匹配效果；偷取转移至攻方；不可驱散拦截。"""
from __future__ import annotations

from pathlib import Path

import pytest

from 战斗模拟.内核.光环运行时 import (
    取光环列表,
    挂载效果,
    匹配驱散类型,
)
from 战斗模拟.内核.流程解释器 import 流程解释器, 构建上下文

FW = Path("/workspace/combat-framework/战斗数值框架.xlsx")


def _mount(side: dict, code: str, **kw):
    ctx = {
        "效果代号": code,
        "叠加规则": "独立",
        "驱散类型等级": kw.get("驱散类型等级", "可驱散"),
        "可窃取": kw.get("可窃取", "否"),
        "标签": kw.get("标签", "魔法"),
        "驱散优先级": kw.get("驱散优先级", 0),
        "到期动作": kw.get("到期动作", ""),
    }
    return 挂载效果(side, code, kw.get("层数", 1), kw.get("时长", 5000), ctx=ctx)


def test_匹配驱散类型_通道与通配():
    assert 匹配驱散类型("魔法", "魔法")
    assert 匹配驱散类型("魔法/诅咒", "诅咒")
    assert 匹配驱散类型("毒", "无")
    assert 匹配驱散类型("物理", "")
    assert not 匹配驱散类型("魔法", "毒")


def test_驱散移除匹配_不可驱散阻断():
    interp = 流程解释器(管线表={})
    atk = {"id": "a", "光环列表": []}
    dfd = {"id": "b", "生命": 1000.0, "光环列表": []}
    _mount(dfd, "可驱Buff", 驱散类型等级="可驱散", 标签="魔法", 驱散优先级=10)
    _mount(dfd, "无敌盾", 驱散类型等级="不可驱散", 标签="魔法", 驱散优先级=99)

    ctx = 构建上下文(
        攻方=atk,
        守方=dfd,
        驱散强度=2,
        驱散类型="魔法",
        驱散优先级="",
    )
    assert interp._call_func("有可驱散效果", "", ctx) is True
    assert interp._call_func("选取可驱散效果", "驱散优先级", ctx) is True
    # 优先级高的是不可驱散（99）
    assert ctx["效果代号"] == "无敌盾"
    assert ctx["驱散类型等级"] == "不可驱散"
    # 管线会因不可驱散跳过；再选下一个
    assert interp._call_func("有可驱散效果", "", ctx) is True
    assert interp._call_func("选取可驱散效果", "驱散优先级", ctx) is True
    assert ctx["效果代号"] == "可驱Buff"
    assert interp._call_func("匹配驱散类型", "标签,驱散类型", ctx) is True
    assert interp._call_func("移除效果", "效果代号", ctx) is True
    codes = {a.效果代号 for a in 取光环列表(dfd)}
    assert "可驱Buff" not in codes
    assert "无敌盾" in codes


def test_偷取转移到攻方():
    interp = 流程解释器(管线表={})
    atk = {"id": "a", "光环列表": []}
    dfd = {"id": "b", "生命": 1000.0, "光环列表": []}
    _mount(dfd, "祝福", 驱散类型等级="可驱散", 标签="魔法", 可窃取="是", 驱散优先级=5)

    ctx = 构建上下文(
        攻方=atk,
        守方=dfd,
        驱散强度=1,
        驱散类型="魔法",
        标记={"可窃取技能"},
    )
    assert interp._call_func("选取可驱散效果", "驱散优先级", ctx) is True
    assert ctx["可窃取"] == "是"
    assert interp._call_func("转移效果", "效果代号,攻方", ctx) is True
    assert 取光环列表(dfd) == []
    assert len(取光环列表(atk)) == 1
    assert 取光环列表(atk)[0].效果代号 == "祝福"


@pytest.mark.skipif(not FW.is_file(), reason="框架表不在 box")
def test_驱散管线对光环运行时生效():
    interp = 流程解释器(工作簿路径=FW)
    if "驱散PVE" not in interp.管线名列表():
        pytest.skip("无驱散PVE管线")
    atk = {"id": "a", "光环列表": [], "生命": 1000.0, "生命上限": 1000.0}
    dfd = {"id": "b", "光环列表": [], "生命": 5000.0, "生命上限": 5000.0, "状态": set(), "标记": set()}
    _mount(dfd, "虚弱", 驱散类型等级="可驱散", 标签="魔法", 驱散优先级=3)
    _mount(dfd, "霸体", 驱散类型等级="不可驱散", 标签="魔法", 驱散优先级=9)

    ctx = 构建上下文(
        攻方=atk,
        守方=dfd,
        驱散强度=2.0,
        驱散类型="魔法",
        驱散优先级="",
        标记=set(),
    )
    result = interp.执行管线("驱散PVE", ctx)
    codes = {a.效果代号 for a in 取光环列表(dfd)}
    assert "虚弱" not in codes
    assert "霸体" in codes
    assert float(result.上下文.get("驱散结果") or ctx.get("驱散结果") or 0) >= 1.0


@pytest.mark.skipif(not FW.is_file(), reason="框架表不在 box")
def test_驱散管线偷取():
    interp = 流程解释器(工作簿路径=FW)
    if "驱散PVE" not in interp.管线名列表():
        pytest.skip("无驱散PVE管线")
    atk = {"id": "a", "光环列表": [], "生命": 1000.0, "生命上限": 1000.0}
    dfd = {"id": "b", "光环列表": [], "生命": 5000.0, "生命上限": 5000.0, "状态": set()}
    _mount(dfd, "强力祝福", 驱散类型等级="可驱散", 标签="魔法", 可窃取="是", 驱散优先级=8)

    ctx = 构建上下文(
        攻方=atk,
        守方=dfd,
        驱散强度=1.0,
        驱散类型="魔法",
        标记={"可窃取技能"},
    )
    interp.执行管线("驱散PVE", ctx)
    assert 取光环列表(dfd) == []
    assert len(取光环列表(atk)) == 1
    assert 取光环列表(atk)[0].效果代号 == "强力祝福"
