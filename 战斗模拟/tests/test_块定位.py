# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from 公共.常量.块名 import 块_流派标准属性面板, 块_模拟器玩法参数
from 公共.工作簿.打开 import 打开工作簿
from 公共.工作簿.块定位 import 查找块原点

WB = Path("/workspace/combat-framework/战斗数值框架.xlsx")


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_find_panel_and_playtime_blocks():
    wb = 打开工作簿(WB)
    try:
        ws = wb["标准模型"]
        r, c = 查找块原点(ws, 块_流派标准属性面板, sheet="标准模型")
        assert r == 1
        r2, c2 = 查找块原点(ws, 块_模拟器玩法参数, sheet="标准模型")
        assert r2 == 1 and c2 == 1
    finally:
        wb.close()
