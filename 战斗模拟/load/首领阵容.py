"""首领阵容：从「场景配置」读取（模式/场景类别=首领）；不依赖已删的「首领对战」表。"""
from __future__ import annotations

from 公共.常量.工作表 import SHEET_场景配置, SHEET_首领对战
from 战斗模拟.load.场景 import 加载场景, _split_list
from 公共.错误 import 数据缺失错误


def 加载首领阵容(wb) -> dict[str, tuple[list[str], list[str]]]:
    """→ {场景名: (友方构筑列表, 敌方/首领列表)}。

    优先：场景配置中 模式==「首领」或 场景类别 含「首领」。
    兼容：若仍存在旧「首领对战」表则一并合并（不强制要求）。
    """
    out: dict[str, tuple[list[str], list[str]]] = {}
    scenes = 加载场景(wb)
    for name, sc in scenes.items():
        raw = sc.原始行 or {}
        mode = str(raw.get("模式") or "").strip()
        cat = str(raw.get("场景类别") or "").strip()
        is_boss = (mode == "首领") or ("首领" in cat) or ("首领" in name)
        if not is_boss:
            continue
        allies = list(sc.友方构筑)
        enemies = list(sc.敌方构筑)
        if not allies:
            allies = _split_list(raw.get("A方构筑列表") or raw.get("A方"))
        if not enemies:
            enemies = _split_list(raw.get("B方构筑列表") or raw.get("B方") or raw.get("首领"))
        out[name] = (allies, enemies)

    # 可选：旧表（已删除时跳过）
    if SHEET_首领对战 in wb.sheetnames:
        try:
            from 公共.常量.工作表 import 表头行, 数据起始行
            from 公共.工作簿.清单页 import 读清单表头, 迭代清单行

            ws = wb[SHEET_首领对战]
            headers = 读清单表头(ws, header_row=表头行(SHEET_首领对战))
            出战列 = ("出战1", "出战2", "出战3", "出战4", "出战5")
            for r, row in 迭代清单行(ws, headers, data_start=数据起始行(SHEET_首领对战)):
                raw = row.get("场景名")
                if raw is None or str(raw).strip() == "":
                    continue
                sname = str(raw).strip()
                boss_raw = row.get("首领")
                if boss_raw is None or str(boss_raw).strip() == "":
                    continue
                allies = []
                for col in 出战列:
                    v = row.get(col)
                    if v is not None and str(v).strip():
                        allies.append(str(v).strip())
                if allies:
                    out.setdefault(sname, (allies, [str(boss_raw).strip()]))
        except 数据缺失错误:
            pass
    return out


# 兼容旧名
加载首领对战 = 加载首领阵容
load_boss_encounters = 加载首领阵容
