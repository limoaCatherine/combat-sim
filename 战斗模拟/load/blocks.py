"""按第 2 行块名、第 3 行字段名读取横排块。"""
from __future__ import annotations

from 战斗模拟.config import DATA_START, HEADER_ROW, META_KEYS


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not str(value).strip())


def block_spans(ws) -> list[tuple[str, int, int]]:
    titles: list[tuple[int, str]] = []
    for col in range(1, (ws.max_column or 1) + 1):
        value = ws.cell(2, col).value
        if not _blank(value):
            titles.append((col, str(value).strip()))
    spans = []
    for i, (start, name) in enumerate(titles):
        end = (titles[i + 1][0] - 1) if i + 1 < len(titles) else (ws.max_column or start)
        if end < start:
            end = start
        spans.append((name, start, end))
    return spans


def _headers(ws, start: int, end: int) -> list[tuple[int, str]]:
    out = []
    for col in range(start, end + 1):
        value = ws.cell(HEADER_ROW, col).value
        if not _blank(value):
            out.append((col, str(value).strip()))
    return out


def read_block(ws, name: str) -> list[dict]:
    span = next((item for item in block_spans(ws) if item[0] == name), None)
    if span is None:
        return []
    _, start, end = span
    headers = _headers(ws, start, end)
    if not headers:
        return []
    key_col = headers[0][0]
    rows = []
    empty = 0
    for row in range(DATA_START, DATA_START + 400):
        key = ws.cell(row, key_col).value
        if _blank(key):
            empty += 1
            if empty > 6:
                break
            continue
        empty = 0
        text = str(key).strip()
        if text in META_KEYS or text.startswith("【"):
            continue
        record = {}
        for col, field in headers:
            value = ws.cell(row, col).value
            if not _blank(value):
                record[field] = value
        if record:
            rows.append(record)
    return rows


def inherit_levels(rows: list[dict], name_key: str, level_key: str) -> list[dict]:
    """等级大于 1 的空单元格继承同名上一等级。"""
    previous: dict[str, dict] = {}
    out = []
    for row in rows:
        name = str(row.get(name_key) or "").strip()
        level = row.get(level_key) or 1
        try:
            level_n = int(level)
        except (TypeError, ValueError):
            level_n = 1
        base = previous.get(name, {})
        merged = dict(base)
        merged.update(row)
        merged[level_key] = level_n
        previous[name] = merged
        out.append(merged)
    return out
