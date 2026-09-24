"""默认框架表路径发现。"""
from __future__ import annotations

from pathlib import Path


def 候选框架路径() -> list[Path]:
    """按常见布局列出候选「战斗数值框架.xlsx」。"""
    here = Path(__file__).resolve()
    # 数值工具/公共/路径.py → 数值工具 → Ro_Inf
    工具根 = here.parent.parent
    ro_inf = 工具根.parent
    names = ("战斗数值框架.xlsx",)
    dirs = [
        Path("/workspace/combat-framework"),
        ro_inf / "数值框架",
        工具根.parent / "数值框架",
        工具根 / "数值框架",
    ]
    out: list[Path] = []
    box = Path("/workspace/combat-framework/战斗数值框架.xlsx").resolve()
    out.append(box)
    classic = (ro_inf / "数值框架" / "战斗数值框架.xlsx").resolve()
    if classic not in out:
        out.append(classic)
    
    import os as _os
    _desk = Path(_os.environ.get("USERPROFILE") or str(Path.home())) / "Desktop"
    for _extra in (
        _desk / "Ro_Inf" / "数值框架",
        _desk / "Limoa" / "Ro_Inf" / "数值框架",
        工具根.parent / "数值框架",
    ):
        if _extra not in dirs:
            dirs.append(_extra)

    for d in dirs:
        for n in names:
            p = (d / n).resolve()
            if p not in out:
                out.append(p)
    return out


def 发现框架路径() -> Path | None:
    for p in 候选框架路径():
        if p.is_file():
            return p
    return None
