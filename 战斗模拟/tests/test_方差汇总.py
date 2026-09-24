# -*- coding: utf-8 -*-
from __future__ import annotations

from 战斗模拟.分析.方差汇总 import 汇总标量, 方差汇总


def test_known_samples_mean_and_p50():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    s = 汇总标量(xs)
    assert s["n"] == 5
    assert abs(s["mean"] - 3.0) < 1e-9
    assert abs(s["p50"] - 3.0) < 1e-9
    assert abs(s["min"] - 1.0) < 1e-9
    assert abs(s["max"] - 5.0) < 1e-9
    # population variance of 1..5 = 2.0
    assert abs(s["var"] - 2.0) < 1e-9


def test_variance_summary_from_dicts():
    samples = [
        {"DPS": 100.0, "HPS": 10.0, "TTK": 20.0},
        {"DPS": 200.0, "HPS": 20.0, "TTK": 10.0},
        {"DPS": 300.0, "HPS": 30.0, "TTK": None},
    ]
    out = 方差汇总(samples)
    assert abs(out["DPS"]["mean"] - 200.0) < 1e-9
    assert abs(out["DPS"]["p50"] - 200.0) < 1e-9
    assert abs(out["HPS"]["mean"] - 20.0) < 1e-9
    assert out["TTK"]["n"] == 2
    assert abs(out["TTK"]["mean"] - 15.0) < 1e-9
