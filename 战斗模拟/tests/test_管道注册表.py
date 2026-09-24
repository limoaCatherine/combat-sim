# -*- coding: utf-8 -*-
from __future__ import annotations

from 战斗模拟.管道.注册表 import 列出管道, 管道注册表
from 战斗模拟.管道.伤害 import 解析伤害PVE


def test_registry_smoke():
    reg = 管道注册表()
    names = 列出管道()
    assert "damage_pve" in names or "伤害PVE" in names
    assert "heal_pve" in names or "治疗PVE" in names
    assert "threat" in names or "伤害仇恨PVE" in names
    assert callable(reg["伤害PVE"])


def test_damage_invuln_zero():
    out = 解析伤害PVE(基础伤害=100.0, defender={"标签": {"无敌"}})
    assert out["伤害"] == 0.0
    assert out["终止"] is True
