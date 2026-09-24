"""仇恨 helper — 已内联进「伤害PVE / 治疗PVE」，非独立流程块。

口径（硬编码，对齐 combat_flow）：
- 伤害仇恨：``(最终伤害+反伤量)*仇恨系数``（表内 设伤害仇恨）
- 治疗仇恨：``治疗值*0.05*仇恨系数``（表内 设治疗仇恨）
本模块保留可调用薄封装：``(伤 × 1.0 + 疗 × 0.05) × 技能仇恨系数``。
"""
from __future__ import annotations

from typing import Any

from 战斗模拟.管道.注册表 import 注册
from 公共.错误 import 数据缺失错误

伤害仇恨系数 = 1.0
治疗仇恨系数 = 0.05


def 解析伤害仇恨PVE(
    *,
    伤害: float = 0.0,
    治疗: float = 0.0,
    技能仇恨系数: float = 1.0,
    **extra: Any,
) -> dict[str, Any]:
    if 技能仇恨系数 is None:
        raise 数据缺失错误("技能仇恨系数缺失，无法结算仇恨")
    coef = float(技能仇恨系数)
    if coef < 0:
        raise 数据缺失错误(f"技能仇恨系数不能为负: {coef}")
    threat = (float(伤害) * 伤害仇恨系数 + float(治疗) * 治疗仇恨系数) * coef
    return {
        "仇恨": threat,
        "伤害": float(伤害),
        "治疗": float(治疗),
        "技能仇恨系数": coef,
        "伤害仇恨系数": 伤害仇恨系数,
        "治疗仇恨系数": 治疗仇恨系数,
        **extra,
    }


注册("threat", 解析伤害仇恨PVE)
注册("伤害仇恨PVE", 解析伤害仇恨PVE)
注册("治疗仇恨PVE", 解析伤害仇恨PVE)

resolve_threat = 解析伤害仇恨PVE
