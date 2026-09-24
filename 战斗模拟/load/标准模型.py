"""标准模型门面：以「流派标准属性面板」为 SSOT（当前框架无 B1/B2）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from 公共.常量.工作表 import SHEET_标准模型
from 战斗模拟.load.面板 import 加载流派面板
from 战斗模拟.load.属性 import 属性面板
from 战斗模拟.load.玩法参数 import 加载玩法参数


@dataclass
class 标准模型:
    构筑列表: list[str] = field(default_factory=list)
    面板: dict[str, 属性面板] = field(default_factory=dict)
    玩法参数: dict[str, Any] = field(default_factory=dict)
    # 兼容旧字段（B2 已移除时为空）
    投放层: list[str] = field(default_factory=list)
    投放行: list[tuple[str, str]] = field(default_factory=list)
    投放: dict[str, dict[str, dict[str, float | None]]] = field(default_factory=dict)
    元数据: dict[str, Any] = field(default_factory=dict)


def 加载标准模型(wb, *, sheet: str = SHEET_标准模型) -> 标准模型:
    panels = 加载流派面板(wb, sheet=sheet)
    builds = list(panels.keys())
    play: dict[str, Any] = {}
    play_err = None
    try:
        play = 加载玩法参数(wb, sheet=sheet)
    except Exception as e:  # noqa: BLE001
        play_err = str(e)
    return 标准模型(
        构筑列表=builds,
        面板=panels,
        玩法参数=play,
        元数据={
            "sheet": sheet,
            "panel_attr_counts": {b: len(p.属性) for b, p in panels.items()},
            "playtime_error": play_err,
            "ssot": "流派标准属性面板",
        },
    )


load_standard_model = 加载标准模型
StandardModel = 标准模型
