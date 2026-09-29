#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按批跑任务打一场。缺生命的对阵会跳过，不写默认血量。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SIBLING_REPOS = ("combat-sim", "scene-coverage", "attr-value", "scene-balance", "numeric-ssot", "doc-format")
for _name in _SIBLING_REPOS:
    _p = ROOT.parent / _name
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))



def main(argv: list[str] | None = None) -> int:
    from 战斗模拟.pipeline import run

    parser = argparse.ArgumentParser(description="战斗模拟")
    parser.add_argument("-w", "--workbook", default=None)
    parser.add_argument("--task", default=None, help="只跑这一条批跑任务")
    parser.add_argument("--write", action="store_true", help="把结果追加到对战模拟的运行结果")
    args = parser.parse_args(argv)
    out = run(args.workbook, task=args.task, write=args.write)
    if not out.get("ok", True):
        print(out.get("原因"))
        return 1
    print(f"技能 {out['技能']}，构筑 {out['构筑']}，任务 {out['任务']}")
    for fight in out["战斗"]:
        print(f"{fight['对阵']}  {fight['时长秒']}秒  伤害 {fight['伤害']}  {fight['胜负']}  指标 {fight.get('指标条数', 0)} 条")
    if out.get("写回行"):
        print(f"长表写至第 {out['写回行']} 行")
    if out.get("矩阵列"):
        print(f"矩阵列 {out['矩阵列']}")
    for item in out.get("跳过") or []:
        print(f"跳过 {item['对阵']}：{item['原因']}")
    pending = out.get("待对齐") or []
    if pending:
        print(f"待对齐 {len(pending)} 条")
        for text in pending[:40]:
            print(f" - {text}")
        if len(pending) > 40:
            print(f" - 其余 {len(pending) - 40} 条未列出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
