"""战斗模拟：框架表路径。不读场景覆盖。"""
from __future__ import annotations

from pathlib import Path

from 公共.路径 import 发现框架路径

SHEET_ATTR = "属性总表"
SHEET_MODEL = "标准模型"
SHEET_MONSTER = "怪物标准模型"
SHEET_SKILL = "技能总表"
SHEET_EFFECT = "效果总表"
SHEET_MASTERY = "精通盘"
SHEET_BUILD = "构筑配置"
SHEET_BEHAVIOR = "行为配置"
SHEET_SCENE = "场景配置"
SHEET_TASK = "对战模拟"

HEADER_ROW = 3
DATA_START = 8
# 第 5–7 行是类型、取值域、说明，不是数据。
META_KEYS = {"文本", "不可空", "必填", "中文主键", "整数", "枚举", "列表", "数值", "表达式"}


def _workbook() -> Path:
    found = 发现框架路径()
    if found is not None and found.is_file():
        return found
    here = Path(__file__).resolve()
    return here.parent.parent.parent / "数值框架" / "战斗数值框架.xlsx"


SIM_WORKBOOK = _workbook()
FRAMEWORK_FILE = SIM_WORKBOOK
