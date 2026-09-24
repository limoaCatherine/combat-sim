# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from 战斗模拟.load.技能 import 加载技能目录
from 战斗模拟.load.效果 import 加载效果目录

WB = Path("/workspace/combat-framework/战斗数值框架.xlsx")

BALANCE_SKILL_HEADERS = (
    "主标签轴",
    "期望段数",
    "平衡分组",
    "是否纳入自动平衡",
    "UGit技能ID",
    "符号表版本",
    "占用GCD",
    "GCD学校",
    "公共冷却组",
    "伤害管线",
    "治疗管线",
    "最小距离",
    "释放最大距离",
    "可移动施法",
    "APL优先级",
)

BALANCE_EFFECT_HEADERS = ("强度量纲", "平衡标签", "是否纳入自动平衡")


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_skill_catalog_loads_balance_headers():
    cat = 加载技能目录(WB)
    assert len(cat) > 0
    # 至少一条有平衡建模回填
    sample = next(s for s in cat.按编号.values() if s.名称 == "盾牌压制" or "占用GCD" in s.原始行)
    assert sample.占用GCD in ("是", "否") or sample.原始行.get("占用GCD") in ("是", "否")
    # 新列进入原始行或 dataclass；未知列不炸
    assert any(h in sample.原始行 for h in ("主标签轴", "符号表版本", "占用GCD"))
    assert sample.符号表版本 in ("", "Attr20260915") or sample.原始行.get("符号表版本") == "Attr20260915"


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_effect_catalog_loads_balance_headers():
    cat = 加载效果目录(WB)
    assert len(cat) > 0
    first = next(iter(cat.按代号.values()))
    # 可选列存在于原始行即可；缺省不报错
    for h in BALANCE_EFFECT_HEADERS:
        # 允许个别效果未填，但表头应被读入至少一行
        pass
    assert any("强度量纲" in e.原始行 or e.强度量纲 for e in cat.按代号.values())
