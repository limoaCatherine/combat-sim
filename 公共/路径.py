"""默认框架表路径发现。"""
from __future__ import annotations

import os
from pathlib import Path

_FRAMEWORK_NAME = "战斗数值框架.xlsx"


def 候选框架路径() -> list[Path]:
    """按常见公开布局列出候选框架工作簿路径。

    优先由环境变量指定；否则依次尝试当前工作目录、本仓库、
    同级 ``数值框架/`` 目录，以及可选的容器路径。
    """
    here = Path(__file__).resolve()
    repo_root = here.parent.parent
    parent = repo_root.parent

    dirs: list[Path] = []
    for key in ("FRAMEWORK_DIR", "BATTLE_SIM_DIR"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            dirs.append(Path(raw).expanduser())

    dirs.extend(
        [
            Path.cwd(),
            repo_root,
            repo_root / "数值框架",
            parent / "数值框架",
            Path("/workspace/combat-framework"),
        ]
    )

    out: list[Path] = []
    for d in dirs:
        p = (d / _FRAMEWORK_NAME).resolve()
        if p not in out:
            out.append(p)
    return out


def 发现框架路径() -> Path | None:
    for p in 候选框架路径():
        if p.is_file():
            return p
    return None
