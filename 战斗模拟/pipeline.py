"""战斗仿真主流程入口（批跑骨架）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from 战斗模拟.批跑 import 跑蒙特卡洛桩
from 战斗模拟.世界 import 加载世界
from 战斗模拟 import config as cfg


def _金标基础伤害(path: Path) -> float:
    from ssot.金标命中 import 金标木桩基础伤害

    return float(金标木桩基础伤害(path))


def run(
    workbook: str | Path | None = None,
    *,
    scene: str = "_smoke_",
    runs: int = 1,
    基础伤害: float | None = None,
) -> dict[str, Any]:
    path = Path(workbook) if workbook else Path(cfg.SIM_WORKBOOK)
    base = 基础伤害 if 基础伤害 is not None else _金标基础伤害(path)
    return 跑蒙特卡洛桩(path, 场景名=scene, 次数=runs, 基础伤害=base)


def load(workbook: str | Path | None = None):
    path = Path(workbook) if workbook else Path(cfg.SIM_WORKBOOK)
    return 加载世界(path)
