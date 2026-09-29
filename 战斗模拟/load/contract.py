"""把模拟器要读的表收成一份契约。不打开场景覆盖。"""
from __future__ import annotations

import openpyxl

from 战斗模拟 import config as cfg
from 战斗模拟.load.blocks import inherit_levels, read_block
from 战斗模拟.load.matrix import load_matrices


def load_contract(path: str | None = None) -> dict:
    book = str(path or cfg.SIM_WORKBOOK)
    wb = openpyxl.load_workbook(book, data_only=False, read_only=False)
    try:
        skills = inherit_levels(_sheet_as_one(wb[cfg.SHEET_SKILL]), "技能名", "技能等级")
        effects = inherit_levels(_sheet_as_one(wb[cfg.SHEET_EFFECT]), "效果名", "效果等级")
        contract = {
            "path": book,
            "skills": {str(r["技能名"]): r for r in skills if r.get("技能名")},
            "effects": {str(r["效果名"]): r for r in effects if r.get("效果名")},
            "mastery": _sheet_as_one(wb[cfg.SHEET_MASTERY]),
            "builds": _sheet_as_one(wb[cfg.SHEET_BUILD]),
            "strategies": read_block(wb[cfg.SHEET_BEHAVIOR], "策略"),
            "phases": read_block(wb[cfg.SHEET_BEHAVIOR], "阶段"),
            "rules": read_block(wb[cfg.SHEET_BEHAVIOR], "规则"),
            "scenes": read_block(wb[cfg.SHEET_SCENE], "场景"),
            "slots": read_block(wb[cfg.SHEET_SCENE], "参战"),
            "mechanics": read_block(wb[cfg.SHEET_SCENE], "机制"),
            "params": {str(r.get("参数名")): r.get("值") for r in read_block(wb[cfg.SHEET_TASK], "模拟参数")},
            "tasks": read_block(wb[cfg.SHEET_TASK], "批跑任务"),
            "metrics": read_block(wb[cfg.SHEET_TASK], "指标定义") or read_block(wb[cfg.SHEET_TASK], "指标"),
            "monsters": read_block(wb[cfg.SHEET_MONSTER], "怪物配置"),
            "panels": _panels(wb[cfg.SHEET_MODEL]),
            "profiles": _profiles(wb[cfg.SHEET_MODEL]),
            "matrices": load_matrices(wb["克制矩阵"]),
            "待对齐": [],
        }
        _merge_scene_row_blocks(wb[cfg.SHEET_SCENE], contract["scenes"])
        _enrich_scene_spacing(contract)
    finally:
        wb.close()
    from 战斗模拟.load.curves import load_curves, load_transfers
    from 战斗模拟.load.xlsx_xml import XmlSheet, read_sheet
    from 战斗模拟.sim.flow import load_pipelines
    from 战斗模拟.sim.spec import compile_specs

    gaps = contract["待对齐"]
    contract["curves"] = load_curves(
        XmlSheet(read_sheet(book, "公式参数", 90)),
        XmlSheet(read_sheet(book, "标准属性", 420)),
        gaps,
    )
    contract["transfers"] = load_transfers(XmlSheet(read_sheet(book, "属性总表", 420)))
    contract["pipes"] = load_pipelines(book)
    compile_specs(contract)
    return contract


def _merge_scene_row_blocks(ws, scenes: list[dict]) -> None:
    """场地/默认站位/默认碰撞与场景同行并列，按行号并进场景记录。"""
    from 战斗模拟.config import DATA_START, HEADER_ROW
    from 战斗模拟.load.blocks import block_spans

    name_span = next((item for item in block_spans(ws) if item[0] == "场景"), None)
    if name_span is None or not scenes:
        return
    _, name_start, name_end = name_span
    name_col = name_start
    for col in range(name_start, name_end + 1):
        if str(ws.cell(HEADER_ROW, col).value or "").strip() == "场景名":
            name_col = col
            break
    by_name = {str(s.get("场景名") or ""): s for s in scenes}
    side_blocks = [item for item in block_spans(ws) if item[0] in ("场地", "默认站位", "默认碰撞")]
    for row in range(DATA_START, DATA_START + 120):
        name = ws.cell(row, name_col).value
        if name in (None, ""):
            continue
        scene = by_name.get(str(name).strip())
        if scene is None:
            continue
        for _, start, end in side_blocks:
            for col in range(start, end + 1):
                field = ws.cell(HEADER_ROW, col).value
                if field in (None, ""):
                    continue
                key = str(field).strip()
                value = ws.cell(row, col).value
                if scene.get(key) in (None, "") and value not in (None, ""):
                    scene[key] = value


def _enrich_scene_spacing(contract: dict) -> None:
    """参战行上的 A/B 间距回填到同名场景（表结构把间距放在参战侧时）。"""
    by_scene: dict[str, dict] = {}
    for slot in contract.get("slots") or []:
        name = str(slot.get("场景名") or "")
        if not name:
            continue
        bag = by_scene.setdefault(name, {})
        for key in ("A间距", "B间距"):
            if bag.get(key) in (None, "") and slot.get(key) not in (None, ""):
                bag[key] = slot.get(key)
    for scene in contract.get("scenes") or []:
        name = str(scene.get("场景名") or "")
        fill = by_scene.get(name) or {}
        for key in ("A间距", "B间距"):
            if scene.get(key) in (None, "") and fill.get(key) not in (None, ""):
                scene[key] = fill[key]


def _profiles(ws) -> dict:
    """只读「流派档案」块，避免同名的属性倾向/面板列把武器、体型盖成数字。"""
    from 战斗模拟.load.blocks import block_spans

    span = next((item for item in block_spans(ws) if item[0] == "流派档案"), None)
    if span is None:
        start, end = 3, 14
    else:
        _, start, end = span
    profiles = {}
    for col in range(start, end + 1):
        name = ws.cell(3, col).value
        if not name or str(name).strip() in ("说明", "项目", "属性用途名", "标准·60级"):
            continue
        # 档案列通常第 4 行是定位文本；跳过空列
        if ws.cell(4, col).value in (None, ""):
            continue
        profiles[str(name).strip()] = _profile_column(ws, col)
    return profiles


def _profile_column(ws, col: int) -> dict:
    """按第 1 列的行名读取，不把种族、体型写死在行号上。"""
    labels = {}
    for row in range(4, 20):
        label = ws.cell(row, 1).value
        if label not in (None, ""):
            labels[str(label).strip()] = ws.cell(row, col).value

    def _text(value):
        if value in (None, ""):
            return None
        # 档案字段必须是文本；数字说明读错了列
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return None
        return str(value).strip()

    return {
        "武器类型": _text(labels.get("武器类型")),
        "施法资源类型": _text(labels.get("施法资源类型")),
        "防御元素": _text(labels.get("防御元素") or labels.get("防御属性类型")),
        "种族": _text(labels.get("种族")),
        "体型": _text(labels.get("体型")),
        "默认移动状态": _text(labels.get("默认移动状态")),
    }


def _sheet_as_one(ws) -> list[dict]:
    """整张表只有字段行、没有可分块时，从第 1 列读到最后一列。"""
    from 战斗模拟.config import DATA_START, HEADER_ROW, META_KEYS

    headers = []
    for col in range(1, (ws.max_column or 1) + 1):
        value = ws.cell(HEADER_ROW, col).value
        if value not in (None, ""):
            headers.append((col, str(value).strip()))
    if not headers:
        return []
    rows = []
    empty = 0
    key_col = headers[0][0]
    for row in range(DATA_START, DATA_START + 400):
        key = ws.cell(row, key_col).value
        if key in (None, ""):
            empty += 1
            if empty > 6:
                break
            continue
        empty = 0
        text = str(key).strip()
        if text in META_KEYS:
            continue
        record = {}
        for col, field in headers:
            value = ws.cell(row, col).value
            if value not in (None, ""):
                record[field] = value
        if record:
            rows.append(record)
    return rows


def _panels(ws) -> dict[str, dict[str, float]]:
    """流派面板：行是属性，列是流派。公式格没有缓存值时该属性缺席。"""
    from 战斗模拟.load.blocks import block_spans

    span = next((item for item in block_spans(ws) if item[0] == "流派面板"), None)
    if span is None:
        return {}
    _, start, end = span
    headers = {}
    for col in range(start, end + 1):
        name = ws.cell(3, col).value
        if name and str(name).strip() not in ("属性用途名", "标准·60级"):
            headers[col] = str(name).strip()
    panels: dict[str, dict[str, float]] = {name: {} for name in headers.values()}
    for row in range(8, 8 + 400):
        attr = ws.cell(start, row).value if False else ws.cell(row, start).value
        if attr in (None, ""):
            continue
        attr_name = str(attr).strip()
        for col, build in headers.items():
            value = ws.cell(row, col).value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                panels[build][attr_name] = float(value)
    return panels
