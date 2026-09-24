"""APL 弱偏置：解析技能表 APL优先级 / APL条件，永不单独决定施放。

条件 DSL（最小子集，未知谓词 → False 并安静跳过）：
  hp_pct < 0.3 | hp_pct > 0.5
  target_hp < 0.25 | target_hp_pct <= 0.2
  gcd_ready
  buff_up(名称) | buff_up:名称
  True / false / 空 → 恒真（仅优先级偏置）
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_CMP = re.compile(
    r"^\s*(?P<lhs>hp_pct|self_hp|自身hp%?|target_hp(?:_pct)?|目标hp%?)\s*"
    r"(?P<op><=|>=|<|>|==|=)\s*(?P<rhs>\d+(?:\.\d+)?%?)\s*$",
    re.I,
)
_BUFF = re.compile(
    r"^\s*buff_up\s*(?:\(\s*([^)]+)\s*\)|:(\S+))\s*$",
    re.I,
)


@dataclass
class APL条目:
    技能: str
    优先级: float = 0.0
    条件: str = ""
    技能编号: str = ""


def _norm_pct(raw: str) -> float:
    s = str(raw).strip()
    if s.endswith("%"):
        return float(s[:-1]) / 100.0
    v = float(s)
    # 约定：>1 且 ≤100 视为百分数写法
    if v > 1.0 and v <= 100.0:
        return v / 100.0
    return v


def _snap_val(snap: Mapping[str, Any], key: str) -> float:
    k = key.lower().replace(" ", "")
    if k in ("hp_pct", "self_hp", "自身hp", "自身hp%"):
        return float(snap.get("自身HP%") if snap.get("自身HP%") is not None else snap.get("hp_pct") or 1.0)
    if k in ("target_hp", "target_hp_pct", "目标hp", "目标hp%"):
        return float(snap.get("目标HP%") if snap.get("目标HP%") is not None else snap.get("target_hp_pct") or 1.0)
    return 0.0


def _cmp(a: float, op: str, b: float) -> bool:
    if op in ("<",):
        return a < b
    if op in ("<=",):
        return a <= b
    if op in (">",):
        return a > b
    if op in (">=",):
        return a >= b
    return abs(a - b) < 1e-9


def 解析条件(条件: str, 快照: Mapping[str, Any]) -> bool:
    """最小条件 DSL；空/True → True；未知谓词 → False（不抛）。"""
    raw = "" if 条件 is None else str(条件).strip()
    if raw in ("", "—", "-", "无", "true", "True", "TRUE", "1"):
        return True
    if raw.lower() in ("false", "0", "否"):
        return False

    # 支持 & / and 合取
    parts = re.split(r"\s*(?:&+|and|&&|；|;)\s*", raw, flags=re.I)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        low = part.lower().replace(" ", "")
        if low in ("gcd_ready", "gcd就绪"):
            rem = float(快照.get("GCD剩余ms") or 快照.get("gcd_ready_ms") or 0.0)
            if rem > 1e-6:
                return False
            continue
        m = _CMP.match(part)
        if m:
            lhs = _snap_val(快照, m.group("lhs"))
            rhs = _norm_pct(m.group("rhs"))
            if not _cmp(lhs, m.group("op"), rhs):
                return False
            continue
        bm = _BUFF.match(part)
        if bm:
            name = (bm.group(1) or bm.group(2) or "").strip()
            buffs = 快照.get("效果") or 快照.get("buffs") or []
            names = {str(x) for x in buffs}
            if name not in names:
                return False
            continue
        # 未知谓词：安静失败
        return False
    return True


def 从技能行解析(行: Mapping[str, Any] | Any, *, 默认优先级: float = 0.0) -> APL条目:
    """从技能表行取 APL优先级 / APL条件。"""
    def _get(obj: Any, *keys: str, default: Any = None) -> Any:
        if isinstance(obj, Mapping):
            for k in keys:
                if k in obj and obj[k] is not None:
                    return obj[k]
            return default
        for k in keys:
            if hasattr(obj, k):
                v = getattr(obj, k)
                if v is not None:
                    return v
        return default

    name = str(_get(行, "名称", "技能名", "技能", default="") or "")
    sid = str(_get(行, "编号", "技能编号", default="") or "")
    pri_raw = _get(行, "APL优先级", "apl", "优先级", default=默认优先级)
    try:
        pri = float(pri_raw) if pri_raw is not None and str(pri_raw).strip() not in ("", "—", "-") else float(默认优先级)
    except (TypeError, ValueError):
        pri = float(默认优先级)
    cond = str(_get(行, "APL条件", "apl条件", "条件", default="") or "")
    return APL条目(技能=name, 优先级=pri, 条件=cond, 技能编号=sid)


def 解析APL表(行列表: list[Any]) -> list[APL条目]:
    return [从技能行解析(r, 默认优先级=-i) for i, r in enumerate(行列表 or [])]


def apl偏置分数(
    技能: Any,
    快照: Mapping[str, Any],
    *,
    epsilon: float = 0.05,
    条目: APL条目 | None = None,
) -> float:
    """条件匹配时返回 ε / max(1, priority_rank) 形式的弱偏置。

    优先级数值越大 → 偏置越大（高技能预设）。
    未匹配条件 → 0。
    """
    if 条目 is None:
        条目 = 从技能行解析(技能)
    if not 解析条件(条目.条件, 快照):
        return 0.0
    # 也接受挂在技能对象上的 apl 字段
    pri = float(条目.优先级)
    if abs(pri) < 1e-12:
        pri = float(getattr(技能, "apl", 0.0) or 0.0)
    if abs(pri) < 1e-12:
        return 0.0
    # 正优先级：ε * pri / (1+|pri|) 封顶；同时兼容「栏位序越小越好」的负值
    if pri > 0:
        rank = max(1.0, pri)
        return float(epsilon) * (rank / (1.0 + rank)) * 2.0  # ~ε..2ε
    # 负优先级：按 |pri| 给极小偏置（栏位打破平局用）
    return float(epsilon) * (pri / (1.0 + abs(pri))) * 0.1


# 英文别名
parse_condition = 解析条件
apl_bias_score = apl偏置分数
parse_apl_table = 解析APL表
