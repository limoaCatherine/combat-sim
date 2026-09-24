"""模拟器玩法参数：跳过 A 列分组标题「— … —」且 B 空的行。"""
from __future__ import annotations

import re
from typing import Any

from 公共.常量.块名 import 块_模拟器玩法参数, 表头_参数名称, 表头_参数值
from 公共.常量.工作表 import SHEET_标准模型
from 公共.工作簿.块定位 import 查找块下表头行, 查找块原点
from 公共.错误 import 数据缺失错误

_GROUP_TITLE = re.compile(r"^[—－\-].*[—－\-]$")


def _is_group_title(name: str) -> bool:
    s = str(name).strip()
    if not s:
        return False
    if _GROUP_TITLE.match(s):
        return True
    if s.startswith("—") or s.startswith("－"):
        return True
    return False


def 加载玩法参数(
    wb,
    *,
    sheet: str = SHEET_标准模型,
) -> dict[str, Any]:
    """→ {参数名称: 参数值}，跳过分组标题行。"""
    if sheet not in wb.sheetnames:
        raise 数据缺失错误(f"缺少工作表: {sheet}")
    ws = wb[sheet]
    br, bc = 查找块原点(ws, 块_模拟器玩法参数, sheet=sheet)
    header_row = 查找块下表头行(
        ws, 块行=br, 块列=bc, 表头=表头_参数名称, sheet=sheet
    )
    out: dict[str, Any] = {}
    empty = 0
    for r in range(header_row + 1, int(ws.max_row or header_row) + 1):
        raw_a = ws.cell(r, bc).value
        raw_b = ws.cell(r, bc + 1).value
        a_empty = raw_a is None or str(raw_a).strip() == ""
        b_empty = raw_b is None or str(raw_b).strip() == ""
        if a_empty and b_empty:
            empty += 1
            if empty >= 3:
                break
            continue
        empty = 0
        if a_empty:
            continue
        name = str(raw_a).strip()
        if _is_group_title(name) and b_empty:
            continue
        if name in (表头_参数名称, 表头_参数值):
            continue
        out[name] = raw_b
    return out
