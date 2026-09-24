"""真实状态决策（主路径）：感知 → 候选 → 一阶路径收益 → 选择动作。

APL 仅作弱偏置 / 高技能预设，永不单独决定施放。
打分可用 EV-lite stub；**执行**仍走真实 RNG（由引擎保证）。
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

from 战斗模拟.ai.APL import apl偏置分数, 从技能行解析
from 战斗模拟.ai.技能价值 import (
    估算基础伤害,
    估算基础治疗,
    感知快照 as _感知快照_kwargs,
)


def 感知快照(
    实体: Any = None,
    世界: Any = None,
    时间轴预告: Any = None,
    *,
    now_ms: float | None = None,
    target: Any = None,
    gcd_ready_at: float = 0.0,
    busy_until: float = 0.0,
    resources: dict[str, float] | None = None,
    buffs: list[str] | None = None,
    distance: float = 1.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """从实体(+可选目标)抽取决策快照。

    兼容两种调用：
      - 感知快照(实体, 世界, 时间轴预告, target=...)
      - 感知快照(now_ms=..., self_hp=..., ...)  ← 旧 kwargs 走 技能价值
    """
    del 世界, 时间轴预告  # 预留：时间轴威胁预告
    if 实体 is None and ("self_hp" in kwargs or "now_ms" in kwargs or now_ms is not None):
        return _感知快照_kwargs(
            now_ms=float(now_ms if now_ms is not None else kwargs.get("now_ms") or 0.0),
            self_hp=float(kwargs.get("self_hp") or 0.0),
            self_hp_max=float(kwargs.get("self_hp_max") or 1.0),
            target_hp=float(kwargs.get("target_hp") or 0.0),
            target_hp_max=float(kwargs.get("target_hp_max") or 1.0),
            gcd_ready_at=float(kwargs.get("gcd_ready_at", gcd_ready_at) or 0.0),
            busy_until=float(kwargs.get("busy_until", busy_until) or 0.0),
            resources=kwargs.get("resources") or resources,
            buffs=kwargs.get("buffs") or buffs,
            distance=float(kwargs.get("distance", distance) or 1.0),
        )

    e = 实体
    t = target
    now = float(now_ms if now_ms is not None else kwargs.get("t") or 0.0)
    self_hp = float(getattr(e, "生命", 0.0) or 0.0)
    self_max = float(getattr(e, "生命上限", 1.0) or 1.0)
    tgt_hp = float(getattr(t, "生命", 0.0) or 0.0) if t is not None else 0.0
    tgt_max = float(getattr(t, "生命上限", 1.0) or 1.0) if t is not None else 1.0
    cds = kwargs.get("cds") or {}
    snap = _感知快照_kwargs(
        now_ms=now,
        self_hp=self_hp,
        self_hp_max=self_max,
        target_hp=tgt_hp,
        target_hp_max=tgt_max,
        gcd_ready_at=float(gcd_ready_at),
        busy_until=float(busy_until),
        resources=resources or {},
        buffs=list(buffs or getattr(e, "效果列表", None) or []),
        distance=float(distance),
    )
    snap["冷却"] = dict(cds)
    snap["目标id"] = getattr(t, "id", None) if t is not None else None
    snap["自身id"] = getattr(e, "id", None) if e is not None else None
    return snap


def 候选技能(
    构筑技能栏: Sequence[Any],
    *,
    可用性过滤: Callable[[Any], bool] | None = None,
    now_ms: float | None = None,
) -> list[Any]:
    """过滤可用性（CD/GCD/资源等由调用方过滤器提供）。"""
    del now_ms
    out: list[Any] = []
    for sk in 构筑技能栏 or []:
        if 可用性过滤 is not None and not 可用性过滤(sk):
            continue
        out.append(sk)
    return out


def 一阶路径收益(
    技能: Any,
    快照: Mapping[str, Any],
    *,
    panel: Mapping[str, Any] | None = None,
    意图权重: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """粗糙 1-ply 路径分：期望伤/疗 stub（打分用，非结算权威）。

    返回 score/dmg/heal/threat/throughput。
    """
    pan = dict(panel or {})
    dmg = 估算基础伤害(技能, pan)
    heal = 估算基础治疗(技能, pan)
    # 也接受直接挂载的 stub 字段（合成测试）
    if dmg <= 0 and hasattr(技能, "期望伤害"):
        try:
            dmg = float(getattr(技能, "期望伤害") or 0.0)
        except (TypeError, ValueError):
            pass
    if heal <= 0 and hasattr(技能, "期望治疗"):
        try:
            heal = float(getattr(技能, "期望治疗") or 0.0)
        except (TypeError, ValueError):
            pass

    threat = dmg * float(getattr(技能, "仇恨系数", 1.0) or 1.0)
    self_hp_pct = float(快照.get("自身HP%") or 1.0)
    tgt_hp_pct = float(快照.get("目标HP%") or 1.0)

    w = {"伤害": 1.0, "治疗": 0.35, "仇恨": 0.0}
    if 意图权重:
        w.update({k: float(v) for k, v in 意图权重.items()})

    heal_util = heal * (1.5 + max(0.0, 0.7 - self_hp_pct) * 3.0)
    dmg_util = dmg * (1.0 + max(0.0, 0.25 - tgt_hp_pct) * 0.8)

    cast = float(getattr(技能, "吟唱毫秒", 0.0) or 0.0)
    action = float(getattr(技能, "动作毫秒", 0.0) or 0.0)
    occupy = getattr(技能, "占用GCD", None)
    if occupy is None:
        raise ValueError("择技需要占用GCD")
    gcd_raw = getattr(技能, "公共冷却毫秒", None)
    if occupy and gcd_raw is None:
        raise ValueError("占用GCD 的技能无公共冷却毫秒")
    gcd = float(gcd_raw or 0.0)
    lock = max(gcd if occupy else 0.0, cast + action)
    if lock <= 0:
        raise ValueError("择技锁时为 0，需要表内动作或公共冷却毫秒")
    throughput = (dmg_util * w["伤害"] + heal_util * w["治疗"] + threat * w["仇恨"]) / (
        lock / 1000.0
    )
    score = float(throughput)
    score -= 0.001 * float(getattr(技能, "栏位序", 0) or 0)

    return {
        "score": score,
        "dmg": float(dmg),
        "heal": float(heal),
        "threat": float(threat),
        "throughput": float(throughput),
        "apl": 0.0,
    }


def 选择动作(
    快照: Mapping[str, Any],
    候选: Sequence[Any],
    *,
    apl偏置: bool | Mapping[str, float] | None = True,
    意图权重: Mapping[str, float] | None = None,
    panel: Mapping[str, Any] | None = None,
    apl_epsilon: float = 0.05,
) -> tuple[Any | None, dict[str, Any]]:
    """选最高分技能；APL 只加小偏置，不能单独覆盖明显更优技能。

    apl偏置:
      - True: 按技能 APL优先级/条件自动算偏置
      - False/None: 不加 APL
      - dict: 技能名 → 额外偏置分
    """
    if not 候选:
        return None, {"候选": [], "理由": "无可用技能"}

    scored: list[tuple[Any, dict[str, float]]] = []
    for sk in 候选:
        detail = 一阶路径收益(sk, 快照, panel=panel, 意图权重=意图权重)
        bias = 0.0
        if apl偏置 is True:
            bias = apl偏置分数(sk, 快照, epsilon=apl_epsilon)
        elif isinstance(apl偏置, Mapping):
            name = str(getattr(sk, "名称", None) or getattr(sk, "技能", sk))
            bias = float(apl偏置.get(name, 0.0) or 0.0)
            # 仍尊重条件（若技能带 APL条件）
            entry = 从技能行解析(sk)
            if entry.条件 and not apl偏置分数(sk, 快照, epsilon=1.0, 条目=entry):
                # 条件不匹配时忽略外部偏置中与条件绑定的部分：仅当条件空才保留
                if entry.条件.strip():
                    from 战斗模拟.ai.APL import 解析条件

                    if not 解析条件(entry.条件, 快照):
                        bias = 0.0
        detail["apl"] = float(bias)
        detail["score"] = float(detail["score"]) + float(bias)
        scored.append((sk, detail))

    scored.sort(key=lambda x: -x[1]["score"])
    best, detail = scored[0]
    return best, {
        "候选": [
            {
                "skill": getattr(s, "名称", str(s)),
                "score": d["score"],
                "base": d["score"] - d["apl"],
                "apl": d["apl"],
                "dmg": d["dmg"],
                "heal": d["heal"],
            }
            for s, d in scored
        ],
        "选中": getattr(best, "名称", str(best)),
        "分数": detail["score"],
        "快照": {
            "自身HP%": 快照.get("自身HP%"),
            "目标HP%": 快照.get("目标HP%"),
            "GCD剩余ms": 快照.get("GCD剩余ms"),
        },
        "理由": detail,
        "决策模式": "状态决策",
    }


# 英文别名
sense_snapshot = 感知快照
candidate_skills = 候选技能
path_benefit_1ply = 一阶路径收益
choose_action = 选择动作
