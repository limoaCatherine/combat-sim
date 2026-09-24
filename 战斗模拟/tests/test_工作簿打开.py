# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

WB = Path("/workspace/combat-framework/战斗数值框架.xlsx")


@pytest.mark.skipif(not WB.is_file(), reason="官方框架表不在 box")
def test_open_workbook():
    from 公共.工作簿.打开 import 打开工作簿

    wb = 打开工作簿(WB)
    try:
        assert "标准模型" in wb.sheetnames
        assert "场景配置" in wb.sheetnames
        assert "首领对战" not in wb.sheetnames  # 已删，首领在场景配置
    finally:
        wb.close()
