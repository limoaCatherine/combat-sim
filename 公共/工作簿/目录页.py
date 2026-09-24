"""六行头目录页读取（R3 字段名，R7 起数据）。"""
from __future__ import annotations

from typing import Any

from 公共.常量.工作表 import 表头行_目录, 数据起始行_目录
from 公共.错误 import 数据缺失错误


def 读表头映射(ws, *, header_row: int = 表头行_目录) -> dict[str, int]:
    headers: dict[str, int] = {}
    for c in range(1, int(ws.max_column or 1) + 1):
        v = ws.cell(header_row, c).value
        if v is None or str(v).strip() == "":
            continue
        name = str(v).strip()
        if name in headers:
            raise 数据缺失错误(f"目录页重复表头列: {name}")
        headers[name] = c
    return headers


def 迭代数据行(
    ws,
    headers: dict[str, int],
    *,
    data_start: int = 数据起始行_目录,
    最大空行: int = 3,
):
    empty = 0
    r = data_start
    while r <= int(ws.max_row or data_start):
        row = {h: ws.cell(r, c).value for h, c in headers.items()}
        if all(v is None or str(v).strip() == "" for v in row.values()):
            empty += 1
            if empty >= 最大空行:
                break
            r += 1
            continue
        empty = 0
        yield r, row
        r += 1


# 英文别名
read_catalog_headers = 读表头映射
iter_catalog_rows = 迭代数据行
