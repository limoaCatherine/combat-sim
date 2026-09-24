"""构筑配置：技能槽只从表读，缺等级不发明 60。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from 公共.常量.工作表 import SHEET_构筑配置
from 公共.错误 import 数据缺失错误


@dataclass
class 技能槽:
    槽位: int
    技能名: str
    等级: int | None = None


@dataclass
class 构筑定义:
    名称: str
    技能栏: list[技能槽] = field(default_factory=list)
    原始行: dict[str, Any] = field(default_factory=dict)


@dataclass
class 构筑目录:
    按名: dict[str, 构筑定义] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.按名)


def _find_header(ws) -> tuple[int, dict[str, int]]:
    for r in range(1, min(9, int(ws.max_row or 1) + 1)):
        headers: dict[str, int] = {}
        for c in range(1, int(ws.max_column or 1) + 1):
            v = ws.cell(r, c).value
            if v is None or str(v).strip() == "":
                continue
            headers[str(v).strip()] = c
        if "构筑名" in headers:
            return r, headers
    raise 数据缺失错误(f"[{SHEET_构筑配置}] 找不到「构筑名」表头")


def 加载构筑(wb) -> 构筑目录:
    if SHEET_构筑配置 not in wb.sheetnames:
        return 构筑目录()
    ws = wb[SHEET_构筑配置]
    header_row, headers = _find_header(ws)
    skill_cols: list[tuple[int, str]] = []
    slot_re = re.compile(r"^技能\s*(\d+)$")
    for name, col in headers.items():
        if not slot_re.match(name):
            continue
        skill_cols.append((col, name))
    skill_cols.sort()
    cat = 构筑目录()
    empty = 0
    for r in range(header_row + 1, int(ws.max_row or header_row) + 1):
        row = {h: ws.cell(r, c).value for h, c in headers.items()}
        raw = row.get("构筑名")
        if raw is None or str(raw).strip() == "":
            empty += 1
            if empty >= 3:
                break
            continue
        empty = 0
        name = str(raw).strip()
        if name in ("木桩",):
            continue
        slots: list[技能槽] = []
        for i, (col, h) in enumerate(skill_cols):
            sk = row.get(h)
            if sk is None or str(sk).strip() in ("", "—", "-", "无"):
                continue
            lv_key = None
            m = slot_re.match(h)
            n = m.group(1) if m else str(i + 1)
            for cand in (f"技能{n}等级", f"技能 {n}等级", h + "等级"):
                if cand in headers:
                    lv_key = cand
                    break
            lv_raw = row.get(lv_key) if lv_key else None
            lv = None
            if lv_raw is not None and str(lv_raw).strip() not in ("", "—", "-"):
                lv = int(float(lv_raw))
            slots.append(技能槽(槽位=i, 技能名=str(sk).strip(), 等级=lv))
        cat.按名[name] = 构筑定义(名称=name, 技能栏=slots, 原始行={k: v for k, v in row.items() if v is not None})
    return cat
