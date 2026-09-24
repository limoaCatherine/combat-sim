# -*- coding: utf-8 -*-
"""Phase D：多目标选取 / 分段 IMPACT / 治疗路由。"""
from __future__ import annotations

from 战斗模拟.内核.事件 import 事件种类
from 战斗模拟.内核.引擎 import 战斗引擎
from 战斗模拟.内核.流程解释器 import 流程解释器
from 战斗模拟.内核.目标选取 import 选取目标
from 战斗模拟.内核.技能路由 import 施放技能
from 战斗模拟.模型.实体 import 实体


def _enemy(eid: str, hp: float = 5000.0, **kw) -> 实体:
    return 实体(
        id=eid,
        名称=eid,
        阵营="敌方",
        生命=hp,
        生命上限=hp,
        等级=60,
        面板={"物理防御": 0.0},
        **kw,
    )


def _ally(eid: str, hp: float = 5000.0, **kw) -> 实体:
    return 实体(
        id=eid,
        名称=eid,
        阵营="友方",
        生命=hp,
        生命上限=max(hp, 10000.0),
        等级=60,
        面板={},
        **kw,
    )


def _drain_impacts(eng: 战斗引擎, *, cap: int = 100) -> list:
    """推进调度器，收集 IMPACT（及命中处理）。"""
    out = []
    n = 0
    while n < cap:
        ev = eng.调度器.推进()
        if ev is None:
            break
        n += 1
        if ev.种类 in (事件种类.命中.value, "IMPACT"):
            src = eng.实体表.get(str((ev.载荷 or {}).get("攻方id") or ""), eng.攻方)
            dst = eng.实体表.get(str((ev.载荷 or {}).get("守方id") or ""), eng.守方)
            if src and dst:
                hit = eng._处理命中(ev, src, dst)
                out.append((ev, hit))
            else:
                out.append((ev, {}))
    return out


def test_cleave_cap_two_of_three_targets():
    atk = 实体(id="A", 名称="攻", 阵营="友方", 生命=10000, 生命上限=10000, 等级=60)
    t1 = _enemy("E1", 5000)
    t2 = _enemy("E2", 4000)
    t3 = _enemy("E3", 3000)
    eng = 战斗引擎(攻方=atk, 守方=t1, 基础伤害=100.0, 解释器=流程解释器(管线表={}), 加载触发表=False)
    eng.实体表 = {e.id: e for e in (atk, t1, t2, t3)}
    eng._种子rng(1)

    skill = {
        "技能名": "顺劈",
        "目标数量上限": 2,
        "次要目标规则": "生命最低",
        "基础伤害": 100.0,
        "伤害管线": "伤害PVE",
        "期望段数": 1,
        "占用GCD": "是",
        "公共冷却时长": 1500,
    }
    summary = eng.施放技能(atk, t1, skill)
    assert summary["目标数"] == 2
    assert len(summary["目标"]) == 2
    assert summary["目标"][0] == "E1"  # 主目标优先
    assert "E3" in summary["目标"]  # 生命最低次要
    assert "E2" not in summary["目标"]
    assert len(summary["命中事件"]) == 2

    impacts = _drain_impacts(eng)
    dmg_impacts = [x for x in impacts if (x[1].get("管线") or "").startswith("伤害") or x[1].get("实际扣血", 0) > 0 or x[0].载荷.get("基础伤害")]
    # 恰好 2 次伤害 IMPACT
    assert len(summary["命中事件"]) == 2
    assert len([i for i in impacts if (i[0].载荷 or {}).get("管线", "").startswith("伤害")]) == 2


def test_two_segments_different_times():
    atk = 实体(id="A", 名称="攻", 阵营="友方", 生命=10000, 生命上限=10000, 等级=60)
    dfd = _enemy("B", 20000)
    eng = 战斗引擎(攻方=atk, 守方=dfd, 基础伤害=50.0, 解释器=流程解释器(管线表={}), 加载触发表=False)
    eng.实体表 = {atk.id: atk, dfd.id: dfd}
    eng._种子rng(2)

    skill = {
        "技能名": "二连斩",
        "目标数量上限": 1,
        "基础伤害": 50.0,
        "期望段数": 2,
        "伤害段间隔": 500,
        "段独立": "是",
        "占用GCD": "否",
    }
    summary = 施放技能(eng, atk, dfd, skill)
    assert len(summary["命中事件"]) == 2

    times = []
    targets = []
    while True:
        ev = eng.调度器.推进()
        if ev is None:
            break
        if ev.种类 in (事件种类.命中.value, "IMPACT"):
            times.append(ev.时间毫秒)
            targets.append((ev.载荷 or {}).get("守方id"))
            eng._处理命中(ev, atk, dfd)

    assert len(times) == 2
    assert times[0] != times[1]
    assert abs(times[1] - times[0] - 500.0) < 1e-6
    assert targets == ["B", "B"]


def test_heal_path_calls_heal_pipe():
    """治疗路由调度 IMPACT(治疗管线)；无 sheet 时走 解析治疗PVE 回退。"""
    healer = _ally("H", 8000.0)
    healer.生命上限 = 10000.0
    target = _ally("T", 3000.0)
    target.生命上限 = 10000.0
    eng = 战斗引擎(
        攻方=healer,
        守方=target,
        基础伤害=0.0,
        解释器=流程解释器(管线表={}),
        加载触发表=False,
    )
    eng.实体表 = {healer.id: healer, target.id: target}
    eng._种子rng(3)

    called = {"n": 0}

    # 包装解释器：即使管线表空，我们用 spy 验证路由载荷；回退路径仍结算治疗
    skill = {
        "技能名": "治疗术",
        "技能类型": "治疗",
        "治疗管线": "治疗PVE",
        "基础治疗": 200.0,
        "目标数量上限": 1,
        "占用GCD": "是",
        "公共冷却时长": 1000,
    }
    summary = eng.施放技能(healer, target, skill)
    assert summary["形态"]["治疗"] is True
    assert summary["形态"]["伤害"] is False
    assert len(summary["命中事件"]) == 1

    impacts = _drain_impacts(eng)
    assert len(impacts) >= 1
    ev, hit = impacts[0]
    assert (ev.载荷 or {}).get("管线") == "治疗PVE"
    assert (ev.载荷 or {}).get("管线请求") == "治疗"
    assert float((ev.载荷 or {}).get("基础治疗") or 0) == 200.0
    assert hit.get("实际治疗", 0) > 0 or hit.get("管线") == "治疗PVE"
    # 生命应上升
    assert target.生命 > 3000.0


def test_select_targets_unit_and_dead_filter():
    atk = 实体(id="A", 阵营="友方", 生命=1000, 生命上限=1000, 等级=60)
    alive = _enemy("E1", 100)
    dead = _enemy("E2", 0)
    dead.存活 = False
    ids = 选取目标(
        atk,
        alive,
        [atk, alive, dead],
        {"目标数量上限": 3, "次要目标规则": "最近"},
    )
    assert "E2" not in ids
    assert ids[0] == "E1"
