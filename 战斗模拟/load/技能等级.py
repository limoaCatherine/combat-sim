"""技能等级行加载（自合并后的技能总表 / 怪物技能；兼容旧独立等级 sheet）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from 公共.常量.工作表 import (
    SHEET_技能总表,
    SHEET_怪物技能,
    SHEET_技能等级_旧,
    SHEET_怪物技能等级_旧,
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
    if v is None or str(v).strip() in ("", "—", "-", "无"):
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
class 技能等级行:
    技能编号: str
    技能名: str = ""
    等级: int = 1
    主消耗量: Any = None
    伤害段: str = ""
    治疗解析式: str = ""
    冷却: float | None = None  # 毫秒
    吟唱: float | None = None
    动作: float | None = None
    公共冷却: float | None = None
    仇恨系数: float | None = None
    效果等级: int | None = None
    段期望系数: float = 1.0
    期望伤害系数: float | None = None
    期望HPS: float | None = None
    等级曲线锚: str = ""
    来源表: str = SHEET_技能总表
    原始行: dict[str, Any] = field(default_factory=dict)
    工作表行号: int = 0


@dataclass
class 技能等级目录:
    """按 (编号, 等级) 索引；另提供按名查找。"""

    按键: dict[tuple[str, int], 技能等级行] = field(default_factory=dict)
    按名键: dict[tuple[str, int], 技能等级行] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.按键)

    def 取(self, 编号或名: str, 等级: int) -> 技能等级行:
        key = (str(编号或名).strip(), int(等级))
        if key in self.按键:
            return self.按键[key]
        if key in self.按名键:
            return self.按名键[key]
        # 回退：取该技能最高不超过请求等级的行
        cands = [r for (c, lv), r in self.按键.items() if c == key[0] and lv <= key[1]]
        cands += [r for (c, lv), r in self.按名键.items() if c == key[0] and lv <= key[1]]
        if cands:
            return max(cands, key=lambda r: r.等级)
        raise 数据缺失错误(f"技能等级不存在: {编号或名}@{等级}")

    def 有(self, 编号或名: str, 等级: int) -> bool:
        try:
            self.取(编号或名, 等级)
            return True
        except 数据缺失错误:
            return False


def _加载一表(ws, *, sheet: str) -> 技能等级目录:
    headers = 读表头映射(ws, header_row=表头行_目录)
    if "技能编号" not in headers:
        raise 数据缺失错误(f"[{sheet}] 缺少列「技能编号」")
    cat = 技能等级目录()
    for r, row in 迭代数据行(ws, headers, data_start=数据起始行_目录):
        code = row.get("技能编号")
        if code is None or str(code).strip() == "":
            continue
        # 跳过类型/说明伪行
        code_s = str(code).strip()
        if code_s in ("文本",) or "主键" in code_s or "唯一" in code_s:
            continue
        lv = _fint(row.get("技能等级") or row.get("等级"), None)
        if lv is None:
            continue
        name = _fstr(row.get("技能名") or code_s)
        entry = 技能等级行(
            技能编号=code_s,
            技能名=name,
            等级=lv,
            主消耗量=row.get("主消耗量"),
            伤害段=_fstr(row.get("伤害段")),
            治疗解析式=_fstr(row.get("治疗解析式")),
            冷却=_ffloat(row.get("冷却时间") or row.get("冷却")),
            吟唱=_ffloat(row.get("吟唱时长") or row.get("吟唱")),
            动作=_ffloat(row.get("动作时长") or row.get("动作")),
            公共冷却=_ffloat(row.get("公共冷却时长") or row.get("公共冷却")),
            仇恨系数=_ffloat(row.get("仇恨系数")),
            效果等级=_fint(row.get("效果等级")),
            段期望系数=_ffloat(row.get("段期望系数"), 1.0) or 1.0,
            期望伤害系数=_ffloat(row.get("期望伤害系数")),
            期望HPS=_ffloat(row.get("期望HPS")),
            等级曲线锚=_fstr(row.get("等级曲线锚")),
            来源表=sheet,
            原始行={k: v for k, v in row.items() if v is not None},
            工作表行号=r,
        )
        cat.按键[(code_s, lv)] = entry
        if name:
            cat.按名键[(name, lv)] = entry
    return cat


def _resolve_sheets(wb, *, 含怪物: bool) -> list[tuple[str, Any]]:
    """优先合并后的总表；若仅有旧独立等级 sheet 则回退。"""
    out: list[tuple[str, Any]] = []
    if SHEET_技能总表 in wb.sheetnames:
        # 合并后：总表含「技能等级」列；若无该列则再试旧 sheet
        ws = wb[SHEET_技能总表]
        headers = 读表头映射(ws, header_row=表头行_目录)
        if "技能等级" in headers or "等级" in headers:
            out.append((SHEET_技能总表, ws))
        elif SHEET_技能等级_旧 in wb.sheetnames:
            out.append((SHEET_技能等级_旧, wb[SHEET_技能等级_旧]))
        else:
            out.append((SHEET_技能总表, ws))
    elif SHEET_技能等级_旧 in wb.sheetnames:
        out.append((SHEET_技能等级_旧, wb[SHEET_技能等级_旧]))
    else:
        raise 数据缺失错误(f"工作簿缺少表: {SHEET_技能总表}")

    if 含怪物:
        if SHEET_怪物技能 in wb.sheetnames:
            ws = wb[SHEET_怪物技能]
            headers = 读表头映射(ws, header_row=表头行_目录)
            if "技能等级" in headers or "等级" in headers:
                out.append((SHEET_怪物技能, ws))
            elif SHEET_怪物技能等级_旧 in wb.sheetnames:
                out.append((SHEET_怪物技能等级_旧, wb[SHEET_怪物技能等级_旧]))
        elif SHEET_怪物技能等级_旧 in wb.sheetnames:
            out.append((SHEET_怪物技能等级_旧, wb[SHEET_怪物技能等级_旧]))
    return out


def 加载技能等级(wb_or_path, *, 含怪物: bool = True) -> 技能等级目录:
    own = False
    if isinstance(wb_or_path, (str, Path)):
        wb = 打开工作簿(wb_or_path, data_only=True)
        own = True
    else:
        wb = wb_or_path
    try:
        sheets = _resolve_sheets(wb, 含怪物=含怪物)
        cat = 技能等级目录()
        for name, ws in sheets:
            part = _加载一表(ws, sheet=name)
            cat.按键.update(part.按键)
            cat.按名键.update(part.按名键)
        if not cat.按键:
            raise 数据缺失错误(f"[{SHEET_技能总表}] 无有效技能等级行（需含「技能等级」列）")
        return cat
    finally:
        if own:
            wb.close()


load_skill_levels = 加载技能等级
SkillLevelRow = 技能等级行
SkillLevelCatalog = 技能等级目录
