# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_公共版本():
    import 公共

    assert 公共.__version__


def test_战斗模拟可导入():
    from 战斗模拟 import 战斗引擎, 事件调度器
    from 战斗模拟.管道.伤害 import DAMAGE_PVE_STAGES, 解析伤害PVE

    assert 战斗引擎 and 事件调度器
    assert len(DAMAGE_PVE_STAGES) == 11
    assert callable(解析伤害PVE)


def test_树内无英文别名包():
    """交付树不得含 limoa_shuzhi / src 双包。"""
    root = Path(__file__).resolve().parents[2]  # 数值工具/
    assert not (root / "limoa_shuzhi").exists()
    assert not (root / "src" / "limoa_shuzhi").exists()
    assert not (root / "src" / "数值工具").exists()
    # 根下也无英文包目录
    assert not any(p.name == "limoa_shuzhi" for p in root.rglob("*") if p.is_dir())
