"""效果总表目录加载（六行头 R3/R7）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from 公共.常量.工作表 import SHEET_效果总表, 表头行_目录, 数据起始行_目录
from 公共.工作簿.打开 import 打开工作簿
from 公共.工作簿.目录页 import 读表头映射, 迭代数据行
from 公共.错误 import 数据缺失错误


@dataclass
class 效果定义:
    代号: str
    效果类型: str = ""
    最大等级: int = 1
    标签: str = ""
    数值类型: str = ""
    效果元素: str = ""
    效果目标: str = ""
    最大层数: int = 1
    # ⑫平衡建模可选列（按中文表头；缺列忽略）
    强度量纲: str = ""
    平衡标签: str = ""
    是否纳入自动平衡: str = ""
    原始行: dict[str, Any] = field(default_factory=dict)


@dataclass
class 效果目录:
    按代号: dict[str, 效果定义] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.按代号)

    def 取(self, 代号: str) -> 效果定义:
        if 代号 not in self.按代号:
            raise 数据缺失错误(f"效果不存在: {代号}")
        return self.按代号[代号]


def _fint(v: Any, default: int = 1) -> int:
    if v is None or str(v).strip() in ("", "—", "-"):
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def 加载效果目录(wb_or_path) -> 效果目录:
    own = False
    if isinstance(wb_or_path, (str, Path)):
        wb = 打开工作簿(wb_or_path, data_only=True)
        own = True
    else:
        wb = wb_or_path
    try:
        if SHEET_效果总表 not in wb.sheetnames:
            raise 数据缺失错误(f"工作簿缺少表: {SHEET_效果总表}")
        ws = wb[SHEET_效果总表]
        headers = 读表头映射(ws, header_row=表头行_目录)
        if "状态代号" not in headers:
            raise 数据缺失错误(f"[{SHEET_效果总表}] 缺少列「状态代号」")
        cat = 效果目录()
        for _r, row in 迭代数据行(ws, headers, data_start=数据起始行_目录):
            code = row.get("状态代号")
            if code is None or str(code).strip() == "":
                continue
            code_s = str(code).strip()
            if code_s in cat.按代号:
                continue  # 效果×等级展开后同代号多行；目录只保留首行
            cat.按代号[code_s] = 效果定义(
                代号=code_s,
                效果类型=str(row.get("效果类型") or "").strip(),
                最大等级=_fint(row.get("最大等级"), 1),
                标签=str(row.get("标签") or "").strip(),
                数值类型=str(row.get("数值类型") or "").strip(),
                效果元素=str(row.get("效果元素") or "").strip(),
                效果目标=str(row.get("效果目标") or "").strip(),
                最大层数=_fint(row.get("最大层数"), 1),
                强度量纲=str(row.get("强度量纲") or "").strip(),
                平衡标签=str(row.get("平衡标签") or "").strip(),
                是否纳入自动平衡=str(row.get("是否纳入自动平衡") or "").strip(),
                原始行={k: v for k, v in row.items() if v is not None},
            )
        if not cat.按代号:
            raise 数据缺失错误(f"[{SHEET_效果总表}] 无有效效果行")
        return cat
    finally:
        if own:
            wb.close()


EffectDef = 效果定义
EffectCatalog = 效果目录
load_effect_catalog = 加载效果目录
