"""按 R1 块标题定位矩阵（不写死行列号）。"""
from __future__ import annotations

from typing import Any

from 公共.错误 import 数据缺失错误


def _cell(ws, r: int, c: int) -> Any:
    return ws.cell(r, c).value


def 查找块原点(ws, 块名: str, *, sheet: str) -> tuple[int, int]:
    """定位块标题单元格 → (row, col)。优先第 1 行，否则扫前 5 行。"""
    want = str(块名).strip()
    max_r = min(5, int(ws.max_row or 1))
    max_c = min(int(ws.max_column or 1), 200)
    for r in range(1, max_r + 1):
        for c in range(1, max_c + 1):
            v = _cell(ws, r, c)
            if v is not None and str(v).strip() == want:
                return r, c
    raise 数据缺失错误(f"[{sheet}] 找不到块标题 {want!r}（应在第 1 行）")


def 查找块下表头行(
    ws,
    *,
    块行: int,
    块列: int,
    表头: str,
    sheet: str,
    扫描行数: int = 12,
) -> int:
    want = str(表头).strip()
    end = min(int(ws.max_row or 1), 块行 + 扫描行数)
    for r in range(块行 + 1, end + 1):
        v = _cell(ws, r, 块列)
        if v is not None and str(v).strip() == want:
            return r
    raise 数据缺失错误(
        f"[{sheet}] 块列 C{块列} 下找不到表头 {want!r}（块起始 R{块行}）"
    )


def 读矩阵(
    ws,
    *,
    表头行: int,
    起始列: int,
    结束列: int | None = None,
    最大空行: int = 3,
) -> list[list[Any]]:
    """从表头下一行起读矩形，遇连续空行停止。"""
    max_c = 结束列 or int(ws.max_column or 起始列)
    rows: list[list[Any]] = []
    empty = 0
    for r in range(表头行 + 1, int(ws.max_row or 表头行) + 1):
        vals = [_cell(ws, r, c) for c in range(起始列, max_c + 1)]
        if all(v is None or str(v).strip() == "" for v in vals):
            empty += 1
            if empty >= 最大空行:
                break
            continue
        empty = 0
        rows.append(vals)
    return rows


# 英文别名
find_block_origin = 查找块原点
find_header_row_under_block = 查找块下表头行
read_matrix = 读矩阵
