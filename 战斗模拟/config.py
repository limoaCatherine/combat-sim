"""战斗模拟：框架表路径与页名（薄封装，数值只来自框架表）。"""
from __future__ import annotations

import os
from pathlib import Path

from 公共.常量 import 工作表 as _ws
from 公共.路径 import 发现框架路径

# === BGRADE_PATH_FIX_BEGIN ===
import os as _bgrade_os
from pathlib import Path as _BgradePath

def _bgrade_resolve_workbook(_file: str):
    """候选序：env → Desktop/Ro_Inf → Desktop/Limoa/Ro_Inf → 同级数值框架 → 旧 FRAMEWORK_DIR。"""
    tools_root = _BgradePath(_file).resolve().parent.parent  # 数值工具
    roinf_legacy = tools_root.parent  # 旧 _ROINF（数值工具在 Desktop 时=Desktop）
    framework_dir_legacy = roinf_legacy / "数值框架"
    env = (_bgrade_os.environ.get("BATTLE_SIM_WORKBOOK") or _bgrade_os.environ.get("LIMOA_FRAMEWORK") or "").strip()
    if env:
        return _BgradePath(env), framework_dir_legacy
    desk = _BgradePath(_bgrade_os.environ.get("USERPROFILE") or str(_BgradePath.home())) / "Desktop"
    candidates = [
        desk / "Ro_Inf" / "数值框架" / "战斗数值框架.xlsx",
        desk / "Limoa" / "Ro_Inf" / "数值框架" / "战斗数值框架.xlsx",
        tools_root.parent / "数值框架" / "战斗数值框架.xlsx",
        tools_root / "数值框架" / "战斗数值框架.xlsx",
        framework_dir_legacy / "战斗数值框架.xlsx",
    ]
    seen = set()
    for c in candidates:
        key = str(c)
        if key in seen:
            continue
        seen.add(key)
        if c.is_file():
            return c, c.parent
    return framework_dir_legacy / "战斗数值框架.xlsx", framework_dir_legacy
# === BGRADE_PATH_FIX_END ===

_ROINF = Path(__file__).resolve().parent.parent.parent
_bgrade_wb, _bgrade_fw = _bgrade_resolve_workbook(__file__)
FRAMEWORK_DIR = _bgrade_fw
ORIGINAL_WORKBOOK = _bgrade_wb
SIM_WORKBOOK = ORIGINAL_WORKBOOK
FORBIDDEN_SHEETS = _ws.禁止页
SHEET_SKILLS = _ws.SHEET_技能总表
SHEET_SCENES = _ws.SHEET_场景配置
SHEET_STANDARD = _ws.SHEET_标准模型
SHEET_FORMULA = _ws.SHEET_公式参数
SHEET_METRICS = _ws.SHEET_战斗模拟指标
HEADER_ROW = _ws.表头行_目录
DATA_START_ROW = _ws.数据起始行_目录
