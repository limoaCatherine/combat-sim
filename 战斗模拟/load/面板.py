"""B3 流派标准属性面板（当前：扁平终值常量）。"""
from __future__ import annotations

from typing import Any

from 公共.常量.块名 import (
    块_流派标准属性面板,
    块_流派标准属性面板_别名,
    表头_属性用途名_别名,
)
from 公共.常量.工作表 import SHEET_标准模型
from 公共.工作簿.块定位 import 查找块下表头行, 查找块原点
from 战斗模拟.load.属性 import 属性面板
from 公共.错误 import 数据缺失错误

_META_离散 = {"武器类型", "种族", "体型", "防御属性类型", "施法资源类型", "默认移动状态"}


def _cell(ws, r: int, c: int) -> Any:
    return ws.cell(r, c).value


def 加载流派面板(
    wb,
    *,
    sheet: str = SHEET_标准模型,
) -> dict[str, 属性面板]:
    """读 B3 → {构筑: 属性面板}。"""
    if sheet not in wb.sheetnames:
        raise 数据缺失错误(f"缺少工作表: {sheet}")
    ws = wb[sheet]
    last_err = None
    br = bc = None
    for nm in 块_流派标准属性面板_别名:
        try:
            br, bc = 查找块原点(ws, nm, sheet=sheet)
            break
        except 数据缺失错误 as e:
            last_err = e
    if br is None or bc is None:
        raise last_err or 数据缺失错误(f"[{sheet}] 找不到 {块_流派标准属性面板}")

    header_row = None
    herr = None
    for hdr in 表头_属性用途名_别名:
        try:
            header_row = 查找块下表头行(ws, 块行=br, 块列=bc, 表头=hdr, sheet=sheet)
            break
        except 数据缺失错误 as e:
            herr = e
    if header_row is None:
        raise herr or 数据缺失错误("B3 无表头")

    builds: list[str] = []
    col_of: dict[str, int] = {}
    for c in range(bc + 1, int(ws.max_column or bc) + 1):
        v = _cell(ws, header_row, c)
        if v is None or str(v).strip() == "":
            if builds:
                break
            continue
        name = str(v).strip()
        col_of[name] = c
        builds.append(name)

    out: dict[str, 属性面板] = {b: 属性面板(构筑=b) for b in builds}
    empty = 0
    for r in range(header_row + 1, int(ws.max_row or header_row) + 1):
        attr_raw = _cell(ws, r, bc)
        if attr_raw is None or str(attr_raw).strip() == "":
            empty += 1
            if empty >= 3:
                break
            continue
        empty = 0
        attr = str(attr_raw).strip()
        if attr in 表头_属性用途名_别名:
            continue
        for b, c in col_of.items():
            raw = _cell(ws, r, c)
            if attr in _META_离散:
                if raw is not None and str(raw).strip() and not (isinstance(raw, str) and raw.startswith("=")):
                    out[b].离散[attr] = str(raw).strip()
                continue
            val: float | None
            if raw is None or str(raw).strip() == "" or (isinstance(raw, str) and raw.startswith("=")):
                val = None
            elif isinstance(raw, (int, float)):
                val = float(raw)
            else:
                try:
                    val = float(str(raw).strip())
                except ValueError:
                    val = None
            out[b].属性[attr] = val
    try:
        from ssot.加载 import 加载转入公式, 加载属性用途名
        from ssot.转入求值 import 覆盖合成面板

        覆盖合成面板(out, 转入=加载转入公式(), 用途名=加载属性用途名())
    except FileNotFoundError:
        pass
    return out


load_playstyle_panel = 加载流派面板
