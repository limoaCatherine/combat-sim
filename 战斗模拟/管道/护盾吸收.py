"""护盾 / 治疗吸收 FIFO 核心 — 解释器与 管道/扣血.py 共用（一份实现）。

主路径（UGit 底 + MMO 常见扩展）：
  · 容量 FIFO + 类型过滤（物理/魔法）
  · 次数盾：护盾次数>0 启用（hits_only / hit_capped 与容量盾并存）
  · 过量转盾：标记「过量转盾开启」时溢出治疗→追加全伤害容量盾
  · 治疗吸收：守方 治疗吸收层 FIFO，治疗先扣吸收再回血
  · 护盾 Buff 绑定 / endBuffOnBreak：破盾时可级联结束来源 Buff
"""
from __future__ import annotations

import math
from typing import Any

# 无穿透伤害类型；仅物理/魔法可被护盾吸收。
_PIERCE_KINDS = frozenset()


def 护盾吸收类型(盾: dict[str, Any] | None) -> str:
    if not isinstance(盾, dict):
        return ""
    for k in ("absorb_type", "护盾吸收类型", "可吸收", "类型", "吸收类型"):
        v = 盾.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def 是穿透护盾的伤害(伤害类型: Any) -> bool:
    """本架构没有穿透护盾的伤害类型。"""
    return False


def 护盾类型可吸收(盾: dict[str, Any] | None, 伤害类型: Any) -> bool:
    """全伤害→物+魔；仅物理/仅魔法匹配；空/无→不可吸收。"""
    if 是穿透护盾的伤害(伤害类型):
        return False
    t = 护盾吸收类型(盾)
    kind = str(伤害类型 or "").strip()
    if not t or t == "无":
        return False
    if t in ("全伤害", "全", "全部", "*", "任意"):
        return kind in ("物理", "物理伤害", "魔法", "魔法伤害")
    if t in ("仅物理", "物理", "物理伤害"):
        return kind in ("物理", "物理伤害")
    if t in ("仅魔法", "魔法", "魔法伤害"):
        return kind in ("魔法", "魔法伤害")
    return False


def _raw_capacity(盾: dict[str, Any]) -> float:
    for k in ("remaining_capacity", "剩余容量", "剩余", "capacity", "容量", "值"):
        if k in 盾 and 盾[k] is not None:
            try:
                return float(盾[k])
            except (TypeError, ValueError):
                pass
    return 0.0


def _raw_hits(盾: dict[str, Any]) -> int:
    for k in ("remaining_hits", "剩余次数", "护盾次数"):
        if k in 盾 and 盾[k] is not None:
            try:
                return int(float(盾[k]))
            except (TypeError, ValueError):
                pass
    return 0


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "是", "真")


def 是次数盾(盾: dict[str, Any] | None) -> bool:
    """hits_only：纯次数盾，整次全挡。

    启用：显式 hits_only=True，或（无 hit_capped）护盾次数>0 且容量≈0。
    """
    if not isinstance(盾, dict):
        return False
    if _truthy(盾.get("hits_only")):
        return True
    if _truthy(盾.get("hit_capped")):
        return False
    if "hits_only" in 盾 and 盾.get("hits_only") is False:
        # 显式关闭 hits_only 时仍可走 hit_capped 推断
        return False
    hits = _raw_hits(盾)
    cap = _raw_capacity(盾)
    return hits > 0 and cap <= 1e-6


def 是次数容量盾(盾: dict[str, Any] | None) -> bool:
    """hit_capped：次数与容量双约束；与容量盾并存。

    启用：显式 hit_capped=True，或 护盾次数>0 且容量>0。
    """
    if not isinstance(盾, dict):
        return False
    if 是次数盾(盾):
        return False
    if _truthy(盾.get("hit_capped")):
        return True
    return _raw_hits(盾) > 0 and _raw_capacity(盾) > 1e-6


def 护盾仍存活(盾: dict[str, Any] | None) -> bool:
    if not isinstance(盾, dict):
        return False
    if _truthy(盾.get("cancelled")) or _truthy(盾.get("已取消")):
        return False
    # 来源 Buff 已结束则跳过（UGit sourceBuff.finished）
    if _truthy(盾.get("source_buff_finished")) or _truthy(盾.get("来源Buff已结束")):
        return False
    if 是次数盾(盾):
        return _raw_hits(盾) > 0
    if 是次数容量盾(盾):
        if _raw_hits(盾) <= 0:
            return False
        return _raw_capacity(盾) > 1e-6
    return _raw_capacity(盾) > 1e-6


def 护盾剩余容量(盾: dict[str, Any] | None) -> float:
    """展示用：hits_only 存活层返回 +inf；否则返回剩余容量。"""
    if not isinstance(盾, dict):
        return 0.0
    if 是次数盾(盾):
        return math.inf if _raw_hits(盾) > 0 else 0.0
    return max(0.0, _raw_capacity(盾))


def _sync_cap(盾: dict[str, Any], rem: float) -> None:
    盾["remaining_capacity"] = rem
    盾["capacity"] = rem
    盾["剩余容量"] = rem
    盾["剩余"] = rem
    盾["容量"] = rem
    盾["值"] = rem


def _sync_hits(盾: dict[str, Any], hits: int) -> None:
    h = max(0, int(hits))
    盾["remaining_hits"] = h
    盾["剩余次数"] = h
    盾["护盾次数"] = h


def 护盾需破盾结束Buff(盾: dict[str, Any] | None) -> bool:
    if not isinstance(盾, dict):
        return False
    return _truthy(盾.get("endBuffOnBreak")) or _truthy(盾.get("破盾结束Buff"))


def 护盾来源Buff代号(盾: dict[str, Any] | None) -> str:
    if not isinstance(盾, dict):
        return ""
    for k in ("source_buff", "来源Buff", "buff_id", "buffId", "效果代号", "绑定Buff"):
        v = 盾.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def 扣减护盾层(盾: dict[str, Any] | None, 吸收量: float) -> float:
    """就地吸收一次伤害，返回未被吸收的溢出。

    - 容量盾：按容量 consume
    - hits_only：消耗 1 次，本击全挡（返回 0）
    - hit_capped：扣次数并按容量吸收
    """
    if not isinstance(盾, dict):
        return float(吸收量)
    amount = float(吸收量)
    if amount <= 0:
        return 0.0
    if not 护盾仍存活(盾):
        return amount

    if 是次数盾(盾):
        _sync_hits(盾, _raw_hits(盾) - 1)
        return 0.0

    rem = _raw_capacity(盾)
    taken = min(amount, max(rem, 0.0))
    if 是次数容量盾(盾):
        hits = _raw_hits(盾)
        if hits > 0:
            _sync_hits(盾, hits - 1)
    _sync_cap(盾, max(0.0, rem - taken))
    return max(0.0, amount - taken)


def 取护盾层(护盾层: list[Any] | None, 游标: int) -> dict[str, Any] | None:
    shields = 护盾层 or []
    idx = int(游标)
    if 0 <= idx < len(shields):
        sh = shields[idx]
        return sh if isinstance(sh, dict) else None
    return None


def 存活护盾列表(护盾层: list[Any] | None) -> list[dict[str, Any]]:
    return [sh for sh in (护盾层 or []) if isinstance(sh, dict) and 护盾仍存活(sh)]


def fifo_护盾吸收(
    shields: list[dict[str, Any]],
    amount: float,
    damage_kind: str,
    *,
    out_broken: list[dict[str, Any]] | None = None,
) -> tuple[float, float, int, list[dict[str, Any]]]:
    """返回 (剩余扣血, 吸收量, 本次破盾数, 存活护盾列表)。

    UGit：REAL/NONE 入站 → 吸收量=0，护盾层原样保留。
    若传入 out_broken，则追加本次破碎层（供 endBuffOnBreak）。
    """
    remaining = float(amount)
    if remaining <= 1e-9:
        alive0 = [sh for sh in shields if isinstance(sh, dict) and 护盾仍存活(sh)]
        return 0.0, 0.0, 0, alive0
    if 是穿透护盾的伤害(damage_kind):
        alive0 = [sh for sh in shields if isinstance(sh, dict) and 护盾仍存活(sh)]
        return remaining, 0.0, 0, alive0

    absorbed = 0.0
    broken = 0
    alive: list[dict[str, Any]] = []
    for sh in shields:
        if remaining <= 1e-9:
            if 护盾仍存活(sh):
                alive.append(sh)
            continue
        if not 护盾仍存活(sh):
            continue
        if not 护盾类型可吸收(sh, damage_kind):
            alive.append(sh)
            continue
        before = remaining
        remaining = 扣减护盾层(sh, remaining)
        absorbed += before - remaining
        if 护盾仍存活(sh):
            alive.append(sh)
        else:
            broken += 1
            if out_broken is not None:
                out_broken.append(sh)
    return remaining, absorbed, broken, alive


def 新建容量盾(
    容量: float,
    *,
    吸收类型: str = "全伤害",
    remaining_hits: int = 0,
    hits_only: bool | None = None,
    hit_capped: bool | None = None,
    endBuffOnBreak: bool = False,
    source_buff: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """构造一层护盾 dict（中英字段对齐）。

    护盾次数>0 时自动按 hits_only / hit_capped 语义启用（可不显式传标志）。
    """
    cap = float(容量)
    hits = int(remaining_hits)
    sh: dict[str, Any] = {
        "absorb_type": 吸收类型,
        "护盾吸收类型": 吸收类型,
        "吸收类型": 吸收类型,
        "remaining_capacity": cap,
        "capacity": cap,
        "剩余容量": cap,
        "剩余": cap,
        "容量": cap,
        "值": cap,
        "remaining_hits": hits,
        "剩余次数": hits,
        "护盾次数": hits,
        "endBuffOnBreak": bool(endBuffOnBreak),
        "破盾结束Buff": bool(endBuffOnBreak),
    }
    if source_buff:
        sh["source_buff"] = str(source_buff)
        sh["来源Buff"] = str(source_buff)
        sh["效果代号"] = str(source_buff)
    if hits_only is True:
        sh["hits_only"] = True
    elif hits_only is False:
        sh["hits_only"] = False
    if hit_capped is True:
        sh["hit_capped"] = True
    elif hit_capped is False:
        sh["hit_capped"] = False
    # 次数>0 且未显式指定：由 是次数盾/是次数容量盾 推断
    sh.update(extra)
    return sh


def _has_mark(ctx: dict[str, Any], name: str) -> bool:
    if ctx.get(name) or ctx.get(f"标记_{name}"):
        return True
    marks = ctx.get("标记") or ctx.get("marks") or ()
    if isinstance(marks, str):
        marks = (marks,)
    return any(str(t) == name for t in marks)


def 执行过量转盾(ctx: dict[str, Any]) -> float:
    """过量治疗转盾（主路径扩展）。须标记「过量转盾开启」。

    溢出→追加全伤害容量盾。返回实际转盾量；写回 ctx['护盾层'] 与结算侧面板。
    """
    amount = 0.0
    for k in ("过量转盾量", "溢出治疗", "过量治疗"):
        if k in ctx and ctx[k] is not None:
            try:
                amount = float(ctx[k])
                if amount > 1e-9:
                    break
            except (TypeError, ValueError):
                pass
    if amount <= 1e-9:
        ctx["过量转盾量"] = 0.0
        return 0.0
    if not _has_mark(ctx, "过量转盾开启"):
        return 0.0

    sh = 新建容量盾(amount, 吸收类型="全伤害")
    layers = ctx.get("护盾层")
    if not isinstance(layers, list):
        layers = []
        ctx["护盾层"] = layers
    layers.append(sh)
    ctx["护盾层"] = layers
    ctx["护盾层数"] = float(len(layers))
    ctx["过量转盾量"] = amount

    role = ctx.get("结算目标") or "守方"
    side = ctx.get(role)
    if isinstance(side, dict):
        if side.get("护盾层") is not layers:
            side["护盾层"] = layers
        ent = side.get("实体") or side.get("entity")
        if ent is not None and hasattr(ent, "护盾层"):
            ent.护盾层 = list(layers)
    return amount


# ---------------------------------------------------------------------------
# 治疗吸收（Heal Absorb）FIFO
# ---------------------------------------------------------------------------


def _heal_absorb_cap(层: dict[str, Any]) -> float:
    for k in ("remaining_capacity", "剩余容量", "剩余", "capacity", "容量", "值"):
        if k in 层 and 层[k] is not None:
            try:
                return float(层[k])
            except (TypeError, ValueError):
                pass
    return 0.0


def 治疗吸收仍存活(层: dict[str, Any] | None) -> bool:
    return isinstance(层, dict) and _heal_absorb_cap(层) > 1e-6


def 存活治疗吸收列表(层列表: list[Any] | None) -> list[dict[str, Any]]:
    return [x for x in (层列表 or []) if 治疗吸收仍存活(x if isinstance(x, dict) else None)]


def 新建治疗吸收层(容量: float, **extra: Any) -> dict[str, Any]:
    cap = float(容量)
    sh: dict[str, Any] = {
        "remaining_capacity": cap,
        "capacity": cap,
        "剩余容量": cap,
        "剩余": cap,
        "容量": cap,
        "值": cap,
    }
    sh.update(extra)
    return sh


def 扣减治疗吸收层(层: dict[str, Any] | None, 吸收量: float) -> float:
    if not isinstance(层, dict):
        return float(吸收量)
    amount = float(吸收量)
    if amount <= 0:
        return 0.0
    rem = _heal_absorb_cap(层)
    taken = min(amount, max(rem, 0.0))
    new_rem = max(0.0, rem - taken)
    层["remaining_capacity"] = new_rem
    层["capacity"] = new_rem
    层["剩余容量"] = new_rem
    层["剩余"] = new_rem
    层["容量"] = new_rem
    层["值"] = new_rem
    return max(0.0, amount - taken)


def 取治疗吸收层(层列表: list[Any] | None, 游标: int) -> dict[str, Any] | None:
    layers = 层列表 or []
    idx = int(游标)
    if 0 <= idx < len(layers):
        sh = layers[idx]
        return sh if isinstance(sh, dict) else None
    return None


def fifo_治疗吸收(
    layers: list[dict[str, Any]],
    heal_amount: float,
) -> tuple[float, float, int, list[dict[str, Any]]]:
    """返回 (剩余可回血治疗, 吸收量, 破碎层数, 存活列表)。"""
    remaining = float(heal_amount)
    if remaining <= 1e-9:
        return 0.0, 0.0, 0, 存活治疗吸收列表(layers)

    absorbed = 0.0
    broken = 0
    alive: list[dict[str, Any]] = []
    for sh in layers:
        if remaining <= 1e-9:
            if 治疗吸收仍存活(sh):
                alive.append(sh)
            continue
        if not 治疗吸收仍存活(sh):
            continue
        before = remaining
        remaining = 扣减治疗吸收层(sh, remaining)
        absorbed += before - remaining
        if 治疗吸收仍存活(sh):
            alive.append(sh)
        else:
            broken += 1
    return remaining, absorbed, broken, alive


def 执行破盾结束Buff(
    ctx: dict[str, Any],
    broken_shields: list[dict[str, Any]] | None,
) -> list[str]:
    """破盾且 endBuffOnBreak 时，级联移除来源 Buff。返回已移除代号列表。"""
    removed: list[str] = []
    if not broken_shields:
        return removed
    role = ctx.get("结算目标") or "守方"
    side = ctx.get(role)
    if not isinstance(side, dict):
        return removed
    try:
        from 战斗模拟.内核 import 光环运行时 as _光环
    except Exception:
        _光环 = None  # type: ignore
    for sh in broken_shields:
        if not 护盾需破盾结束Buff(sh):
            continue
        code = 护盾来源Buff代号(sh)
        if not code:
            continue
        if _光环 is not None:
            try:
                _光环.移除效果(side, code)
            except Exception:
                # 降级：直接从面板光环列表剔除
                auras = side.get("光环") or side.get("auras") or []
                if isinstance(auras, list):
                    side["光环"] = [
                        a
                        for a in auras
                        if not (
                            isinstance(a, dict)
                            and str(a.get("效果代号") or a.get("id") or "") == code
                        )
                    ]
        removed.append(code)
    if removed:
        ctx["破盾结束Buff列表"] = list(ctx.get("破盾结束Buff列表") or []) + removed
    return removed


# 英文别名
can_absorb = 护盾类型可吸收
remaining_capacity = 护盾剩余容量
absorb_one = 扣减护盾层
shield_alive = 护盾仍存活
fifo_shield_absorb = fifo_护盾吸收
make_capacity_shield = 新建容量盾
apply_overheal_to_shield = 执行过量转盾
is_hits_only = 是次数盾
is_hit_capped = 是次数容量盾
damage_pierces_shield = 是穿透护盾的伤害
fifo_heal_absorb = fifo_治疗吸收
make_heal_absorb = 新建治疗吸收层
apply_end_buff_on_break = 执行破盾结束Buff
