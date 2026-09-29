"""按单元格流式读取 xlsx。公式单元格保留公式文本，供表达式抽取。"""
from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_CELL = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_COL = re.compile(r"([A-Z]+)(\d+)")


def _col(ref: str) -> int:
    match = _COL.match(ref)
    number = 0
    for char in match.group(1):
        number = number * 26 + (ord(char) - 64)
    return number


def _strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    out = []
    for item in root.findall("m:si", _NS):
        out.append("".join(node.text or "" for node in item.iter(_CELL + "t")))
    return out


def _sheets(archive: zipfile.ZipFile) -> dict[str, str]:
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {}
    for rel in rels:
        target = rel.attrib["Target"].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        targets[rel.attrib["Id"]] = target
    found = {}
    for sheet in book.findall("m:sheets/m:sheet", _NS):
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        found[sheet.attrib["name"]] = targets[rid]
    return found


def _text(cell, strings: list[str]) -> str:
    formula = cell.find("m:f", _NS)
    if formula is not None and formula.text and not str(formula.text).startswith("IFERROR(Xklc"):
        # 计算公式列需要公式文本；系数格仍读缓存值。
        if cell.attrib.get("r", "").startswith("C"):
            return formula.text
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        inline = cell.find("m:is", _NS)
        return "" if inline is None else "".join(node.text or "" for node in inline.iter(_CELL + "t"))
    value = cell.find("m:v", _NS)
    if value is None or value.text is None:
        if formula is not None and formula.text:
            return formula.text
        return ""
    if kind == "s":
        return strings[int(value.text)]
    return value.text


def read_sheet(path: str, sheet: str, max_row: int = 500) -> dict[int, dict[int, str]]:
    with zipfile.ZipFile(path) as archive:
        strings = _strings(archive)
        target = _sheets(archive)[sheet]
        rows: dict[int, dict[int, str]] = {}
        for _event, element in ET.iterparse(archive.open(target), events=("end",)):
            if element.tag != _CELL + "row":
                continue
            index = int(element.attrib.get("r", "0"))
            if index > max_row:
                element.clear()
                break
            cells = {}
            for cell in element.findall("m:c", _NS):
                ref = cell.attrib.get("r", "")
                if not ref:
                    continue
                text = _text(cell, strings).strip()
                if text:
                    cells[_col(ref)] = text
            rows[index] = cells
            element.clear()
        return rows


class XmlSheet:
    """让按 cell(row, col).value 读取的装载函数不用再走 openpyxl。"""

    def __init__(self, rows: dict[int, dict[int, str]]):
        self._rows = rows

    def cell(self, row: int, col: int):
        return _Value(self._rows.get(row, {}).get(col))


class _Value:
    def __init__(self, value):
        self.value = None if value in (None, "") else _coerce(value)


def _coerce(value: str):
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value
