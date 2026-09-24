"""技能总表目录加载（六行头 R3/R7）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from 公共.常量.工作表 import SHEET_技能总表, 表头行_目录, 数据起始行_目录
from 公共.工作簿.打开 import 打开工作簿
from 公共.工作簿.目录页 import 读表头映射, 迭代数据行
from 公共.错误 import 数据缺失错误


@dataclass
class 技能定义:
    编号: str
    名称: str = ""
    技能类型: str = ""
    最大等级: int = 1
    职业归属: str = ""
    武器归属: str = ""
    技能标签: str = ""
    仇恨系数: float = 1.0
    数值类型: str = ""
    元素: str = ""
    # ⑭平衡建模 / UGit 对口可选列（按中文表头读取；缺列忽略）
    占用GCD: str = ""
    GCD学校: str = ""
    公共冷却组: str = ""
    伤害管线: str = ""
    治疗管线: str = ""
    最小距离: Any = None
    释放最大距离: Any = None
    可移动施法: str = ""
    APL优先级: Any = None
    主标签轴: str = ""
    期望段数: Any = None
    平衡分组: str = ""
    是否纳入自动平衡: str = ""
    UGit技能ID: Any = None
    符号表版本: str = ""
    原始行: dict[str, Any] = field(default_factory=dict)


@dataclass
class 技能目录:
    按编号: dict[str, 技能定义] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.按编号)

    def 取(self, 编号: str) -> 技能定义:
        if 编号 not in self.按编号:
            raise 数据缺失错误(f"技能不存在: {编号}")
        return self.按编号[编号]


def _ffloat(v: Any, default: float = 1.0) -> float:
    if v is None or str(v).strip() in ("", "—", "-"):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fint(v: Any, default: int = 1) -> int:
    if v is None or str(v).strip() in ("", "—", "-"):
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def 加载技能目录(wb_or_path) -> 技能目录:
    own = False
    if isinstance(wb_or_path, (str, Path)):
        wb = 打开工作簿(wb_or_path, data_only=True)
        own = True
    else:
        wb = wb_or_path
    try:
        if SHEET_技能总表 not in wb.sheetnames:
            raise 数据缺失错误(f"工作簿缺少表: {SHEET_技能总表}")
        ws = wb[SHEET_技能总表]
        headers = 读表头映射(ws, header_row=表头行_目录)
        if "技能编号" not in headers:
            raise 数据缺失错误(f"[{SHEET_技能总表}] 缺少列「技能编号」")
        cat = 技能目录()
        for _r, row in 迭代数据行(ws, headers, data_start=数据起始行_目录):
            code = row.get("技能编号")
            if code is None or str(code).strip() == "":
                continue
            code_s = str(code).strip()
            if code_s in cat.按编号:
                continue  # 技能×等级展开后同 ID 多行；目录只保留首行
            threat = _ffloat(row.get("仇恨系数"), 1.0)
            cat.按编号[code_s] = 技能定义(
                编号=code_s,
                名称=str(row.get("技能名") or code_s).strip(),
                技能类型=str(row.get("技能类型") or "").strip(),
                最大等级=_fint(row.get("最大等级"), 1),
                职业归属=str(row.get("职业归属") or "").strip(),
                武器归属=str(row.get("武器归属") or "").strip(),
                技能标签=str(row.get("技能标签") or "").strip(),
                仇恨系数=threat,
                数值类型=str(row.get("数值类型") or "").strip(),
                元素=str(row.get("元素") or "").strip(),
                占用GCD=str(row.get("占用GCD") or "").strip(),
                GCD学校=str(row.get("GCD学校") or "").strip(),
                公共冷却组=str(row.get("公共冷却组") or "").strip(),
                伤害管线=str(row.get("伤害管线") or "").strip(),
                治疗管线=str(row.get("治疗管线") or "").strip(),
                最小距离=row.get("最小距离"),
                释放最大距离=row.get("释放最大距离"),
                可移动施法=str(row.get("可移动施法") or "").strip(),
                APL优先级=row.get("APL优先级"),
                主标签轴=str(row.get("主标签轴") or "").strip(),
                期望段数=row.get("期望段数"),
                平衡分组=str(row.get("平衡分组") or "").strip(),
                是否纳入自动平衡=str(row.get("是否纳入自动平衡") or "").strip(),
                UGit技能ID=row.get("UGit技能ID"),
                符号表版本=str(row.get("符号表版本") or "").strip(),
                原始行={k: v for k, v in row.items() if v is not None},
            )
        if not cat.按编号:
            raise 数据缺失错误(f"[{SHEET_技能总表}] 无有效技能行")
        return cat
    finally:
        if own:
            wb.close()


SkillDef = 技能定义
SkillCatalog = 技能目录
load_skill_catalog = 加载技能目录
