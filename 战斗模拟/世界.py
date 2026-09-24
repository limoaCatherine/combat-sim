"""世界数据轻量容器（批跑骨架）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from 公共.工作簿.打开 import 打开工作簿
from 战斗模拟.load.场景 import 加载场景, 场景定义
from 战斗模拟.load.标准模型 import 加载标准模型, 标准模型
from 战斗模拟.load.首领阵容 import 加载首领阵容


@dataclass
class 世界数据:
    路径: Path
    表名列表: list[str] = field(default_factory=list)
    场景: dict[str, 场景定义] = field(default_factory=dict)
    标准模型: 标准模型 | None = None
    首领阵容: dict[str, tuple[list[str], list[str]]] = field(default_factory=dict)
    公式参数: Any = None
    技能目录: Any = None
    效果目录: Any = None
    技能等级: Any = None
    构筑: Any = None
    原始: dict[str, Any] = field(default_factory=dict)


def 加载世界(
    path: str | Path,
    *,
    data_only: bool = True,
    加载公式: bool = True,
    加载技能效果: bool = False,
) -> 世界数据:
    p = Path(path)
    wb = 打开工作簿(p, data_only=data_only)
    try:
        scenes = 加载场景(wb)
        sm = 加载标准模型(wb)
        bosses = 加载首领阵容(wb)
        fp = None
        skills = None
        effects = None
        skill_lv = None
        builds = None
        if 加载公式:
            try:
                from 战斗模拟.load.公式参数 import 加载公式参数

                fp = 加载公式参数(wb)
            except Exception:  # noqa: BLE001
                fp = None
        if 加载技能效果:
            from 战斗模拟.load.技能 import 加载技能目录
            from 战斗模拟.load.效果 import 加载效果目录
            from 战斗模拟.load.技能等级 import 加载技能等级
            from 战斗模拟.load.构筑 import 加载构筑

            skills = 加载技能目录(wb)
            effects = 加载效果目录(wb)
            skill_lv = 加载技能等级(wb)
            builds = 加载构筑(wb)
        return 世界数据(
            路径=p,
            表名列表=list(wb.sheetnames),
            场景=scenes,
            标准模型=sm,
            首领阵容=bosses,
            公式参数=fp,
            技能目录=skills,
            效果目录=effects,
            技能等级=skill_lv,
            构筑=builds,
        )
    finally:
        wb.close()


load_world = 加载世界
WorldData = 世界数据
