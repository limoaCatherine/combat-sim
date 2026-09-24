"""效果等级行加载（自合并后的效果总表 / 怪物效果；兼容旧独立等级 sheet）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from 公共.常量.工作表 import (
    SHEET_效果总表,
    SHEET_怪物效果,
    SHEET_效果等级_旧,
    SHEET_怪物效果等级_旧,
    表头行_目录,
    数据起始行_目录,
)
from 公共.工作簿.打开 import 打开工作簿
from 公共.工作簿.目录页 import 读表头映射, 迭代数据行
from 公共.错误 import 数据缺失错误


def _ffloat(v: Any, default: float | None = None) -> float | None:
    if v is None or str(v).strip() in ("", "—", "-", "无"):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fint(v: Any, default: int | None = None) -> int | None:
    if v is None or str(v).strip() in ("", "—", "-"):
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _fstr(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ("—", "-") else s


@dataclass
class 效果等级行:
    状态代号: str
    等级: int = 1
    效果解析式: str = ""
    护盾吸收量: str = ""
    修正表达式: str = ""
    效果时间: float | None = None  # 毫秒
    原始行: dict[str, Any] = field(default_factory=dict)


@dataclass
class 效果等级目录:
    按键: dict[tuple[str, int], 效果等级行] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.按键)

    def 取(self, 代号: str, 等级: int) -> 效果等级行 | None:
        key = (str(代号).strip(), int(等级))
        if key in self.按键:
            return self.按键[key]
        cands = [r for (c, lv), r in self.按键.items() if c == key[0] and lv <= key[1]]
        return max(cands, key=lambda r: r.等级) if cands else None


def _加载一表(ws) -> 效果等级目录:
    headers = 读表头映射(ws, header_row=表头行_目录)
    code_key = "状态代号" if "状态代号" in headers else (
        "效果代号" if "效果代号" in headers else None
    )
    if not code_key:
        raise 数据缺失错误("效果表缺少状态代号列")
    cat = 效果等级目录()
    for _r, row in 迭代数据行(ws, headers, data_start=数据起始行_目录):
        code = row.get(code_key)
        if code is None or str(code).strip() == "":
            continue
        code_s = str(code).strip()
        lv = _fint(row.get("效果等级"), 1) or 1
        cat.按键[(code_s, lv)] = 效果等级行(
            状态代号=code_s,
            等级=lv,
            效果解析式=_fstr(row.get("效果解析式")),
            护盾吸收量=_fstr(row.get("护盾吸收量")),
            修正表达式=_fstr(row.get("修正表达式")),
            效果时间=_ffloat(row.get("效果时间") or row.get("持续时长") or row.get("持续时间")),
            原始行={k: v for k, v in row.items() if v is not None},
        )
    return cat


def _resolve_sheets(wb, *, 含怪物: bool) -> list:
    out = []
    if SHEET_效果总表 in wb.sheetnames:
        ws = wb[SHEET_效果总表]
        headers = 读表头映射(ws, header_row=表头行_目录)
        if "效果等级" in headers:
            out.append(ws)
        elif SHEET_效果等级_旧 in wb.sheetnames:
            out.append(wb[SHEET_效果等级_旧])
        else:
            # 合并表但缺等级列：仍按效果总表读（默认等级 1）
            out.append(ws)
    elif SHEET_效果等级_旧 in wb.sheetnames:
        out.append(wb[SHEET_效果等级_旧])

    if 含怪物:
        if SHEET_怪物效果 in wb.sheetnames:
            out.append(wb[SHEET_怪物效果])
        elif SHEET_怪物效果等级_旧 in wb.sheetnames:
            out.append(wb[SHEET_怪物效果等级_旧])
    return out


def 加载效果等级(wb_or_path, *, 含怪物: bool = True) -> 效果等级目录:
    own = False
    if isinstance(wb_or_path, (str, Path)):
        wb = 打开工作簿(wb_or_path, data_only=True)
        own = True
    else:
        wb = wb_or_path
    try:
        cat = 效果等级目录()
        for ws in _resolve_sheets(wb, 含怪物=含怪物):
            part = _加载一表(ws)
            cat.按键.update(part.按键)
        return cat
    finally:
        if own:
            wb.close()


load_effect_levels = 加载效果等级
