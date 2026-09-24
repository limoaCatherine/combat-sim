#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划入口：启动_首领对战.py"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Optional, cast

if hasattr(sys.stdout, "reconfigure"):
    cast(io.TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    cast(io.TextIOWrapper, sys.stderr).reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SIBLING_REPOS = ("combat-sim", "scene-coverage", "attr-value", "scene-balance", "numeric-ssot", "doc-format")
for _name in _SIBLING_REPOS:
    _p = ROOT.parent / _name
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def main(argv: Optional[list[str]] = None) -> int:
    """薄封装：走战斗模拟批跑，默认挑场景配置中的首领场景。"""
    from 战斗模拟.世界 import 加载世界
    from 战斗模拟.pipeline import run
    from 战斗模拟 import config as cfg

    ap = argparse.ArgumentParser(description="首领对战（场景配置·首领）")
    ap.add_argument("-w", "--workbook", default=None)
    ap.add_argument("-s", "--scene", default=None, help="指定首领场景名")
    ap.add_argument("-n", "--runs", type=int, default=1)
    args = ap.parse_args(argv)
    wb = args.workbook or str(cfg.SIM_WORKBOOK)
    world = 加载世界(wb)
    scene = args.scene
    if not scene:
        if world.首领阵容:
            scene = next(iter(world.首领阵容))
        else:
            print({"错误": "未找到首领场景", "场景数": len(world.场景)})
            return 1
    print({"首领阵容": {k: {"友方": v[0], "首领": v[1]} for k, v in world.首领阵容.items()}})
    out = run(wb, scene=scene, runs=args.runs)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

