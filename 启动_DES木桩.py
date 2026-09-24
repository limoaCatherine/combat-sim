
def _publish_out(name: str):
    from pathlib import Path
    dest = Path(__file__).resolve().parents[0] / "out" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金标技能经 DES 引擎打一次木桩；基础伤害与命中位只来自技能总表+标准模型。"""
from __future__ import annotations

import io
import json
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
    del argv
    from ssot import 框架路径
    from ssot.实体工厂 import 从框架构建木桩对
    from ssot.金标命中 import 加载金标技能行, _基础伤害
    from 战斗模拟.内核.引擎 import 战斗引擎

    path = 框架路径()
    rows = 加载金标技能行(path)
    if not rows:
        print("技能总表无金标行")
        return 5
    row = rows[0]
    atk, dfd = 从框架构建木桩对(path, 构筑名="正面铁壁")
    base = _基础伤害(row, atk.面板)
    hit_pos = str(row.get("命中位") or "").strip()
    dtype = str(row.get("数值类型") or "").strip()
    if not dtype:
        print("金标行无数值类型")
        return 5
    eng = 战斗引擎(
        工作簿路径=path,
        攻方=atk,
        守方=dfd,
        基础伤害=base,
        伤害类型=dtype,
        强制命中=(hit_pos == "必中"),
        命中位=hit_pos or None,
        上限毫秒=1.0,
        加载触发表=False,
    )
    r = eng.run_once(seed=0)
    dest = _publish_out("des_gold.json")
    dest.write_text(
        json.dumps(
            {
                "技能": row.get("技能名"),
                "构筑": atk.名称,
                "基础伤害": base,
                "命中位": hit_pos,
                "数值类型": dtype,
                "伤害总量": r.伤害总量,
                "时长毫秒": r.时长毫秒,
                "事件数": r.事件数,
                "守方剩余生命": dfd.生命,
                "木桩生命上限": dfd.生命上限,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"伤害总量": r.伤害总量, "事件数": r.事件数, "写出": str(dest)}, ensure_ascii=False))
    return 0 if r.伤害总量 else 5


if __name__ == "__main__":
    raise SystemExit(main())
