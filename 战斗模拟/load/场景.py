# -*- coding: utf-8 -*-
"""场景配置骨架。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from 公共.常量.工作表 import SHEET_场景配置
from 公共.错误 import 数据缺失错误


class 场景定义(BaseModel):
    名称: str
    友方构筑: list[str] = Field(default_factory=list)
    敌方构筑: list[str] = Field(default_factory=list)
    样本数: int = 1
    战斗时长秒: float | None = None
    复现种子: int | None = None
    模式: str = ""
    原始行: dict = Field(default_factory=dict)


def _split_list(raw) -> list[str]:
    if raw is None:
        return []
    s = str(raw).strip()
    if not s or s in ("无", "-", "—"):
        return []
    for sep in ("|", "；", ";", "、", ","):
        if sep in s:
            return [p.strip() for p in s.split(sep) if p.strip()]
    return [s]


def _find_scene_header(ws) -> tuple[int, dict[str, int]]:
    """扫描前 30 行，定位含「场景名」的表头行。"""
    for r in range(1, min(31, int(ws.max_row or 1) + 1)):
        headers: dict[str, int] = {}
        for c in range(1, int(ws.max_column or 1) + 1):
            v = ws.cell(r, c).value
            if v is None or str(v).strip() == "":
                continue
            headers[str(v).strip()] = c
        if "场景名" in headers:
            return r, headers
    raise 数据缺失错误(f"[{SHEET_场景配置}] 找不到「场景名」表头行")


def 加载场景(wb) -> dict[str, 场景定义]:
    if SHEET_场景配置 not in wb.sheetnames:
        return {}
    ws = wb[SHEET_场景配置]
    try:
        header_row, headers = _find_scene_header(ws)
    except 数据缺失错误:
        return {}
    out: dict[str, 场景定义] = {}
    empty = 0
    for r in range(header_row + 1, int(ws.max_row or header_row) + 1):
        row = {h: ws.cell(r, c).value for h, c in headers.items()}
        raw = row.get("场景名")
        if raw is None or str(raw).strip() == "":
            empty += 1
            if empty >= 3:
                break
            continue
        empty = 0
        name = str(raw).strip()
        row_type = str(row.get("行类型") or "").strip()
        if row_type != "场景":
            continue
        allies = _split_list(row.get("A方构筑列表") or row.get("A方") or row.get("友方"))
        enemies = _split_list(row.get("B方构筑列表") or row.get("B方") or row.get("敌方"))
        samples = None
        for sk in ("蒙特卡洛模拟次数", "样本数", "次数", "MC次数"):
            if sk in row and row[sk] is not None and str(row[sk]).strip() not in ("", "—", "-"):
                try:
                    samples = int(float(row[sk]))
                except (TypeError, ValueError):
                    samples = None
                break
        if samples is None:
            samples = 1
        dur = row.get("战斗时长秒")
        dur_f = None
        if dur is not None and str(dur).strip() not in ("", "—", "-"):
            dur_f = float(dur)
        seed = row.get("复现种子")
        if seed is None or str(seed).strip() in ("", "—", "-"):
            seed = row.get("随机种子")
        seed_i = int(float(seed)) if seed is not None and str(seed).strip() not in ("", "—", "-") else None
        out[name] = 场景定义(
            名称=name,
            友方构筑=allies,
            敌方构筑=enemies,
            样本数=samples,
            战斗时长秒=dur_f,
            复现种子=seed_i,
            模式=str(row.get("模式") or "").strip(),
            原始行={k: v for k, v in row.items() if v is not None},
        )
    return out


def 取场景(scenes: dict[str, 场景定义], name: str) -> 场景定义:
    if name not in scenes:
        可选 = "、".join(sorted(scenes)[:20]) or "(无)"
        raise 数据缺失错误(f"场景不存在: {name}；可选: {可选}")
    return scenes[name]


def 默认木桩场景名(scenes: dict[str, 场景定义] | None) -> str | None:
    if not scenes:
        return None
    for key in ("木桩", "木桩打击", "标准木桩"):
        if key in scenes:
            return key
    return None


load_scenes = 加载场景
get_scene = 取场景
SceneDef = 场景定义
