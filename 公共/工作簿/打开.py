"""openpyxl 打开助手（无 freeze_panes 顾虑）。"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.workbook.workbook import Workbook as WorkbookType

from 公共.错误 import 配置错误, 数据缺失错误


def 打开工作簿(
    path: str | Path,
    *,
    data_only: bool = True,
    read_only: bool = False,
) -> WorkbookType:
    p = Path(path)
    if not p.is_file():
        raise 配置错误(f"找不到工作簿: {p}")
    try:
        return load_workbook(p, data_only=data_only, read_only=read_only)
    except Exception as e:  # noqa: BLE001
        raise 数据缺失错误(f"无法打开工作簿 {p}: {e}") from e


# 英文别名
open_workbook = 打开工作簿
