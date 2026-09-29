"""元素克制和体型克制。守方行、攻方列。"""
from __future__ import annotations


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def load_matrices(ws) -> dict:
    element = {}
    size = {}
    title_row = None
    for row in range(1, 8):
        for col in range(1, 30):
            if str(ws.cell(row, col).value or "").strip() == "元素克制":
                title_row = row
                break
        if title_row:
            break
    if title_row:
        header = title_row + 1
        cols = {}
        for col in range(2, 16):
            name = ws.cell(header, col).value
            if not _blank(name):
                cols[col] = str(name).strip()
        for row in range(header + 1, header + 14):
            defender = ws.cell(row, 1).value
            if _blank(defender):
                continue
            element[str(defender).strip()] = {}
            for col, attacker in cols.items():
                value = ws.cell(row, col).value
                if isinstance(value, (int, float)):
                    element[str(defender).strip()][attacker] = float(value)
    size_title = None
    for row in range(1, 8):
        for col in range(1, 30):
            if str(ws.cell(row, col).value or "").strip() == "体型克制":
                size_title = (row, col)
                break
    if size_title:
        row, col = size_title
        header = row + 1
        cols = {}
        for c in range(col + 1, col + 6):
            name = ws.cell(header, c).value
            if not _blank(name):
                cols[c] = str(name).strip()
        for r in range(header + 1, header + 20):
            weapon = ws.cell(r, col).value
            if _blank(weapon):
                continue
            size[str(weapon).strip()] = {}
            for c, body in cols.items():
                value = ws.cell(r, c).value
                if isinstance(value, (int, float)):
                    size[str(weapon).strip()][body] = float(value)
    return {"元素": element, "体型": size}


def element_rate(matrices: dict, attack: str, defense: str) -> float:
    if not attack or attack == "无元素" and defense in (None, "", "无", "无元素"):
        return 1.0
    table = matrices.get("元素") or {}
    row = table.get(defense or "无元素") or table.get("无元素") or {}
    return float(row.get(attack, row.get("无元素", 1.0)) or 1.0)


def size_rate(matrices: dict, weapon: str, body: str) -> float:
    table = matrices.get("体型") or {}
    row = table.get(weapon or "") or {}
    return float(row.get(body, 1.0) or 1.0)
