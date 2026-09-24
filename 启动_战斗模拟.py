#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划入口：启动_战斗模拟.py"""
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
    from 战斗模拟.pipeline import run
    from 战斗模拟 import config as cfg

    ap = argparse.ArgumentParser(description="战斗模拟（木桩/场景批跑骨架）")
    ap.add_argument("-w", "--workbook", default=None, help="战斗数值框架.xlsx")
    ap.add_argument("-s", "--scene", default="_smoke_", help="场景名（默认 _smoke_ 冒烟）")
    ap.add_argument("-n", "--runs", type=int, default=1, help="次数")
    args = ap.parse_args(argv)
    wb = args.workbook or str(cfg.SIM_WORKBOOK)
    out = run(wb, scene=args.scene, runs=args.runs)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

