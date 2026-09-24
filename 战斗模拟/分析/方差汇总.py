"""MC 样本方差 / 分位汇总（DPS / HPS / TTK 等）。"""
from __future__ import annotations

import math
import statistics
from typing import Any, Iterable, Mapping, Sequence


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    return float(s[f] * (c - k) + s[c] * (k - f))


def 汇总标量(样本: Sequence[float | None] | Iterable[float | None]) -> dict[str, float | None]:
    """mean / var / std / CV / p05 / p50 / p95 / min / max / n。"""
    vals = [float(x) for x in 样本 if x is not None]
    if not vals:
        return {
            "mean": None,
            "var": None,
            "std": None,
            "cv": None,
            "p05": None,
            "p50": None,
            "p95": None,
            "min": None,
            "max": None,
            "n": 0,
        }
    mean = statistics.fmean(vals)
    var = statistics.pvariance(vals) if len(vals) > 1 else 0.0
    std = math.sqrt(var)
    cv = (std / mean) if abs(mean) > 1e-12 else None
    return {
        "mean": mean,
        "var": var,
        "std": std,
        "cv": cv,
        "p05": _percentile(vals, 5),
        "p50": _percentile(vals, 50),
        "p95": _percentile(vals, 95),
        "min": min(vals),
        "max": max(vals),
        "n": len(vals),
    }


def 方差汇总(
    样本列表: Sequence[Mapping[str, Any]] | Sequence[float],
    *,
    字段: Sequence[str] = ("DPS", "HPS", "TTK"),
) -> dict[str, Any]:
    """从 run 样本 dict 列表提取字段并汇总；若传入纯 float 列表则作为单一 ``value``。"""
    if not 样本列表:
        return {k: 汇总标量([]) for k in 字段}

    first = 样本列表[0]
    if isinstance(first, (int, float)) or first is None:
        return {"value": 汇总标量(样本列表)}  # type: ignore[arg-type]

    out: dict[str, Any] = {}
    for key in 字段:
        xs = [row.get(key) if isinstance(row, Mapping) else None for row in 样本列表]
        out[key] = 汇总标量(xs)
    out["n"] = len(样本列表)
    return out


# 英文别名
summarize_scalar = 汇总标量
variance_summary = 方差汇总
