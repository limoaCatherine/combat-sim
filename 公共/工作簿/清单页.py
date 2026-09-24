"""清单页读取（R4 字段名，R5 起数据）。"""
from __future__ import annotations

from 公共.常量.工作表 import 表头行_清单, 数据起始行_清单
from 公共.工作簿.目录页 import 迭代数据行, 读表头映射


def 读清单表头(ws, *, header_row: int = 表头行_清单) -> dict[str, int]:
    return 读表头映射(ws, header_row=header_row)


def 迭代清单行(ws, headers: dict[str, int], *, data_start: int = 数据起始行_清单):
    yield from 迭代数据行(ws, headers, data_start=data_start)


read_list_headers = 读清单表头
iter_list_rows = 迭代清单行
