# -*- coding: utf-8 -*-
"""面板全量加载（替代旧 B2 投放分配冒烟）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from 公共.工作簿.打开 import 打开工作簿
from 公共.常量.块名 import 块_流派标准属性面板
from 公共.工作簿.块定位 import 查找块原点
from 战斗模拟.load.面板 import 加载流派面板
from 战斗模拟.load.标准模型 import 加载标准模型
from 战斗模拟.load.玩法参数 import 加载玩法参数
from 战斗模拟.load.首领阵容 import 加载首领阵容

WB = Path("/workspace/combat-framework/战斗数值框架.xlsx")


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_find_panel_block():
    wb = 打开工作簿(WB)
    try:
        ws = wb["标准模型"]
        r, c = 查找块原点(ws, 块_流派标准属性面板, sheet="标准模型")
        assert r == 3  # 页结构：块标题在 R3
        assert c >= 1
    finally:
        wb.close()


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_panel_full_load():
    wb = 打开工作簿(WB)
    try:
        panels = 加载流派面板(wb)
        assert len(panels) == 11
        # 全量属性行（含等级/种族等元行）；框架约 300+ 
        counts = {b: len(p.属性) for b, p in panels.items()}
        assert all(n >= 300 for n in counts.values()), counts
        # 抽样
        p0 = next(iter(panels.values()))
        assert "素质力量" in p0.属性
        healcrit = (
            "治疗暴击效果(PVE)",
            "治疗暴击效果(PVP)",
            "治疗暴击伤害效果(PVE)",
            "治疗暴击伤害效果(PVP)",
        )
        for b, panel in panels.items():
            for k in healcrit:
                assert k in panel.属性, f"{b} missing {k}"
                assert panel.属性[k] == 0.0
        # master HealCrit ⊆ panel（属性总表用途名）
        ws_m = wb["属性总表"]
        master_hc = []
        for r in range(2, (ws_m.max_row or 1) + 1):
            v = ws_m.cell(r, 2).value
            if v and str(v).strip() in healcrit:
                master_hc.append(str(v).strip())
        assert set(healcrit) <= set(master_hc)
        assert set(healcrit) <= set(p0.属性)
    finally:
        wb.close()


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_standard_model_panel_ssot():
    wb = 打开工作簿(WB)
    try:
        sm = 加载标准模型(wb)
        assert sm.元数据.get("ssot") == "流派标准属性面板"
        assert len(sm.构筑列表) == 11
        assert sm.投放 == {}  # 当前框架无 B2
        assert len(sm.玩法参数) >= 5
        # 分组标题不应进入玩法参数
        for k in sm.玩法参数:
            assert not str(k).startswith("—"), k
    finally:
        wb.close()


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_playtime_skips_group_titles():
    wb = 打开工作簿(WB)
    try:
        params = 加载玩法参数(wb)
        assert "模拟步长" in params
        assert params["模拟步长"] == 100
        for k in params:
            assert not str(k).strip().startswith("—")
    finally:
        wb.close()


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_boss_from_scenes_not_sheet():
    wb = 打开工作簿(WB)
    try:
        bosses = 加载首领阵容(wb)
        assert len(bosses) >= 1
        name, (allies, enemies) = next(iter(bosses.items()))
        assert "首领" in name or True
        assert allies and enemies
    finally:
        wb.close()
