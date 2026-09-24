"""从「公式参数」表加载对抗率 k/c 与效果模板（骨架）。

折算口径：``率 = X / (X + k·Lv + c)``，只衰弱、不另卡设计顶。

加载策略：
- 优先 ``data_only=True`` 读取已由 Excel 缓存的 k/c 数值；
- 若缓存为空（未 CalculateFull），仍可用公式簿填充「计算公式」等文本列；
- 「效果下限/效果上限」随表头一并进入 ``原始行``。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from 公共.常量.工作表 import SHEET_公式参数
from 公共.工作簿.打开 import 打开工作簿
from 公共.错误 import 数据缺失错误


def 折算对抗率(X: float, k: float, c: float, 等级: float) -> float:
    """``X / (X + k·Lv + c)``；X≤0 时返回 0。"""
    x = float(X)
    if x <= 0:
        return 0.0
    den = x + float(k) * float(等级) + float(c)
    if den <= 0:
        return 0.0
    return x / den


@dataclass(frozen=True)
class 对抗曲线:
    名称: str
    k: float
    c: float
    取值类型: str = "率值"
    对应毕业属性: str = ""


@dataclass
class 公式参数表:
    """对抗率曲线 + 原始行（效果值公式等后续接线）。"""

    曲线: dict[str, 对抗曲线] = field(default_factory=dict)
    效果公式: dict[str, str] = field(default_factory=dict)
    原始行: list[dict[str, Any]] = field(default_factory=list)
    k_c缓存缺失: bool = False

    def 取曲线(self, 名称: str) -> 对抗曲线:
        if 名称 in self.曲线:
            return self.曲线[名称]
        # 别名：物理免伤率% ↔ 物理免伤率
        alts = []
        if 名称.endswith("%"):
            alts.append(名称[:-1])
        else:
            alts.append(名称 + "%")
        for a in alts:
            if a in self.曲线:
                return self.曲线[a]
        raise 数据缺失错误(f"公式参数缺少对抗率曲线: {名称}")

    def 有曲线(self, 名称: str) -> bool:
        try:
            self.取曲线(名称)
            return True
        except 数据缺失错误:
            return False

    def 折算(self, 名称: str, X: float, 等级: float) -> float:
        cur = self.取曲线(名称)
        return 折算对抗率(X, cur.k, cur.c, 等级)


def _fnum(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "—", "-", "无", "N/A", "n/a"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _找表头(ws) -> tuple[int, dict[str, int]]:
    for r in range(1, min(30, int(ws.max_row or 1) + 1)):
        headers: dict[str, int] = {}
        for c in range(1, int(ws.max_column or 1) + 1):
            v = ws.cell(r, c).value
            if v is None or str(v).strip() == "":
                continue
            headers[str(v).strip()] = c
        if "参数名" in headers or "名称" in headers:
            if "取值类型" in headers or "类型" in headers:
                return r, headers
    raise 数据缺失错误(f"[{SHEET_公式参数}] 找不到参数名/取值类型表头")


def _attr_col(headers: dict[str, int]) -> int | None:
    return (
        headers.get("对应属性用途名")
        or headers.get("对应毕业属性(量)")
        or headers.get("对应毕业属性")
    )


def _扫表(ws, out: 公式参数表, *, 填曲线: bool, 填效果公式: bool) -> None:
    header_row, headers = _找表头(ws)
    name_col = headers.get("参数名") or headers.get("名称")
    type_col = headers.get("取值类型") or headers.get("类型")
    k_col = headers.get("对抗率·等级系数k") or headers.get("等级系数k") or headers.get("k")
    c_col = headers.get("对抗率·等级常数c") or headers.get("等级常数c") or headers.get("c")
    formula_col = headers.get("计算公式")
    attr_col = _attr_col(headers)

    empty = 0
    for r in range(header_row + 1, int(ws.max_row or header_row) + 1):
        name_raw = ws.cell(r, name_col).value if name_col else None
        if name_raw is None or str(name_raw).strip() == "":
            empty += 1
            if empty >= 3:
                break
            continue
        empty = 0
        name = str(name_raw).strip()
        typ = str(ws.cell(r, type_col).value or "").strip() if type_col else ""
        row: dict[str, Any] = {"参数名": name, "取值类型": typ, "_row": r}
        for h, c in headers.items():
            row[h] = ws.cell(r, c).value
        # 原始行：公式簿与缓存簿都写；缓存簿优先覆盖数值列
        if 填曲线:
            # data_only pass — authoritative for 原始行 numeric snapshot
            out.原始行.append(row)
        elif not out.原始行:
            out.原始行.append(row)
        else:
            # merge formula-mode text into existing 原始行 by name
            for existing in out.原始行:
                if existing.get("参数名") == name:
                    for h, c in headers.items():
                        v = ws.cell(r, c).value
                        # Prefer non-empty formula/text when cached was None
                        if existing.get(h) is None and v is not None:
                            existing[h] = v
                        # Always refresh 计算公式 from formula sheet (plaintext DSL)
                        if h == "计算公式" and v is not None:
                            existing[h] = v
                    break

        if 填曲线 and typ == "率值" and k_col and c_col:
            k = _fnum(ws.cell(r, k_col).value)
            c_val = _fnum(ws.cell(r, c_col).value)
            if k is not None and c_val is not None:
                attr = ""
                if attr_col:
                    attr = str(ws.cell(r, attr_col).value or "").strip()
                out.曲线[name] = 对抗曲线(
                    名称=name, k=float(k), c=float(c_val), 取值类型=typ, 对应毕业属性=attr
                )

        if 填效果公式 and formula_col:
            f = ws.cell(r, formula_col).value
            if f is not None and str(f).strip() not in ("", "—", "-"):
                base = name
                for suf in ("(PVE)", "(PVP)"):
                    if base.endswith(suf):
                        base = base[: -len(suf)]
                        break
                text = str(f).strip()
                out.效果公式[name] = text
                out.效果公式.setdefault(base, text)


def 加载公式参数(wb_or_path) -> 公式参数表:
    """从工作簿或路径加载「公式参数」。

    路径输入时：先 data_only 取 k/c；再开公式簿补「计算公式」等。
    若 Excel 公式缓存为空，``曲线`` 可能为空并设 ``k_c缓存缺失=True``
    （需本机 Excel CalculateFull 后重存）。
    """
    out = 公式参数表()

    if isinstance(wb_or_path, (str, Path)):
        path = Path(wb_or_path)
        wb_cached = 打开工作簿(path, data_only=True)
        try:
            if SHEET_公式参数 not in wb_cached.sheetnames:
                raise 数据缺失错误(f"工作簿缺少表: {SHEET_公式参数}")
            _扫表(wb_cached[SHEET_公式参数], out, 填曲线=True, 填效果公式=True)
        finally:
            wb_cached.close()

        # 公式簿：补计算公式文本（率值 C 列为 Excel 公式时 data_only 可能是算后字符串）
        wb_f = 打开工作簿(path, data_only=False)
        try:
            _扫表(wb_f[SHEET_公式参数], out, 填曲线=False, 填效果公式=True)
        finally:
            wb_f.close()

        if not out.曲线:
            out.k_c缓存缺失 = True
            # 仍要求至少有原始行；效果公式可无缓存使用
            if not out.原始行:
                raise 数据缺失错误(f"[{SHEET_公式参数}] 未解析到任何数据行")
            # 不在此处 raise：调用方可检查 k_c缓存缺失；取曲线仍会失败
        return out

    # 已打开的工作簿：按调用方 data_only 设置一次性扫描
    wb = wb_or_path
    if SHEET_公式参数 not in wb.sheetnames:
        raise 数据缺失错误(f"工作簿缺少表: {SHEET_公式参数}")
    _扫表(wb[SHEET_公式参数], out, 填曲线=True, 填效果公式=True)
    if not out.曲线:
        out.k_c缓存缺失 = True
        if not out.原始行:
            raise 数据缺失错误(f"[{SHEET_公式参数}] 未解析到任何数据行")
    return out


# 英文别名
convert_opposed_rate = 折算对抗率
FormulaParams = 公式参数表
load_formula_params = 加载公式参数
