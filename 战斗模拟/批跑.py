"""批跑：MC 真实战斗（默认）+ 可选独立 EV 分析。"""
from __future__ import annotations

import math
import statistics
from pathlib import Path
from typing import Any

from 战斗模拟.内核.引擎 import 战斗引擎
from 战斗模拟.内核.技能引擎 import 技能战斗引擎
from 战斗模拟.世界 import 加载世界, 世界数据
from 战斗模拟.load.场景 import 取场景, 默认木桩场景名
from 公共.错误 import 数据缺失错误


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


def _agg(xs: list[float | None]) -> dict[str, float | None]:
    vals = [float(x) for x in xs if x is not None]
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


def 跑蒙特卡洛桩(
    workbook: str | Path,
    *,
    场景名: str,
    次数: int = 1,
    world: 世界数据 | None = None,
    基础伤害: float | None = None,
) -> dict[str, Any]:
    """单次 IMPACT 结算；基础伤害必须来自金标/调用方，禁止默认 100。"""
    if 基础伤害 is None:
        raise 数据缺失错误("跑蒙特卡洛桩 需要基础伤害（金标伤害段或显式传入）")
    w = world or 加载世界(workbook)
    if not w.场景 and 场景名:
        if 场景名 != "_smoke_":
            raise 数据缺失错误(
                f"工作簿未解析到任何场景，且请求场景={场景名!r}。"
                f"表名列表={w.表名列表}"
            )
    elif 场景名 != "_smoke_":
        取场景(w.场景, 场景名)

    results = []
    total_dmg = 0.0
    for i in range(max(1, 次数)):
        eng = 战斗引擎(w, 上限毫秒=1_000.0, 基础伤害=基础伤害)
        once = eng.run_once(seed=i)
        results.append(once.to_dict())
        total_dmg += float(once.伤害总量)

    return {
        "场景": 场景名,
        "次数": 次数,
        "表名数": len(w.表名列表),
        "场景数": len(w.场景),
        "构筑数": len(w.标准模型.构筑列表) if w.标准模型 else 0,
        "伤害总量": total_dmg,
        "平均伤害": total_dmg / max(1, 次数),
        "metrics": {
            "runs": 次数,
            "伤害总量": total_dmg,
            "平均伤害": total_dmg / max(1, 次数),
            "stub": False,
            "samples": results,
        },
    }


def _跑一轮场景(
    w: 世界数据,
    *,
    场景名: str,
    次数: int,
    seed: int,
    期望模式: bool,
    收集sample: bool,
) -> dict[str, Any]:
    sc = 取场景(w.场景, 场景名)
    allies = sc.友方构筑 or []
    enemies = list(sc.敌方构筑 or [])
    if not allies:
        raise 数据缺失错误(f"场景 {场景名} 无 A 方构筑")
    if not enemies:
        raise 数据缺失错误(f"场景 {场景名} 无 B 方构筑，禁止默认木桩")
    atk_name = allies[0]
    dfd_name = enemies[0]
    if sc.战斗时长秒 is None:
        raise 数据缺失错误(f"场景 {场景名} 无战斗时长秒")
    duration_ms = float(sc.战斗时长秒) * 1000.0
    if sc.复现种子 is None and seed is None:
        raise 数据缺失错误(f"场景 {场景名} 无复现种子")
    base_seed = int(seed if seed is not None else sc.复现种子)

    samples: list[dict[str, Any]] = []
    dps_list: list[float] = []
    hps_list: list[float] = []
    dmg_list: list[float] = []
    event_list: list[int] = []
    ttk_list: list[float | None] = []
    gcd_list: list[float] = []
    last_sample_log: list[dict[str, Any]] = []
    last_share: dict[str, float] = {}
    last_metrics: dict[str, Any] = {}
    # MC: stochastic rolls; EV: 期望模式 + 强制命中 for stable coeff
    强制命中 = bool(期望模式)

    for i in range(max(1, 次数)):
        eng = 技能战斗引擎(
            w,
            攻方构筑=atk_name,
            守方构筑=dfd_name,
            上限毫秒=duration_ms,
            期望模式=期望模式,
            强制命中=强制命中,
            模式=sc.模式 or "PVE",
        )
        once = eng.run_once(seed=base_seed + i)
        m = once.指标
        dps_list.append(float(m.get("DPS") or 0.0))
        hps_list.append(float(m.get("HPS") or 0.0))
        dmg_list.append(float(once.伤害总量))
        event_list.append(int(once.事件数))
        ttk_list.append(m.get("TTK"))
        gcd_list.append(float(m.get("GCD利用率") or 0.0))
        last_metrics = m
        last_share = dict(m.get("技能伤害占比") or {})
        if 收集sample:
            last_sample_log = list(m.get("sample") or [])
        samples.append(
            {
                "seed": base_seed + i,
                "DPS": m.get("DPS"),
                "HPS": m.get("HPS"),
                "伤害总量": once.伤害总量,
                "事件数": once.事件数,
                "时长毫秒": once.时长毫秒,
                "TTK": m.get("TTK"),
                "GCD利用率": m.get("GCD利用率"),
            }
        )

    path_label = "EV" if 期望模式 else "MC"
    return {
        "路径": path_label,
        "期望模式": 期望模式,
        "场景": 场景名,
        "次数": 次数,
        "seed": base_seed,
        "攻方构筑": atk_name,
        "守方构筑": dfd_name,
        "战斗时长秒": sc.战斗时长秒,
        "模式": sc.模式,
        "DPS": _agg(dps_list),
        "HPS": _agg(hps_list),
        "伤害总量": _agg(dmg_list),
        "TTK": _agg(ttk_list),
        "GCD利用率": _agg(gcd_list),
        "事件数": _agg([float(x) for x in event_list]),
        "技能伤害占比": last_share,
        "技能伤害": last_metrics.get("技能伤害"),
        "技能治疗": last_metrics.get("技能治疗"),
        "施法次数": last_metrics.get("施法次数"),
        "sample": last_sample_log if 收集sample else [],
        "runs": samples,
        "metrics": {
            "路径": path_label,
            "runs": 次数,
            "DPS": _agg(dps_list)["mean"],
            "HPS": _agg(hps_list)["mean"],
            "伤害总量": _agg(dmg_list)["mean"],
            "TTK": _agg(ttk_list)["mean"],
            "GCD利用率": _agg(gcd_list)["mean"],
            "事件数": _agg([float(x) for x in event_list])["mean"],
            "时长毫秒": last_metrics.get("时长毫秒"),
            "技能伤害占比": last_share,
            "方差": {
                "DPS": _agg(dps_list),
                "HPS": _agg(hps_list),
                "伤害总量": _agg(dmg_list),
                "TTK": _agg(ttk_list),
            },
            "stub": False,
            "引擎": "技能战斗引擎",
            "samples": samples,
        },
    }


def 跑场景战斗(
    workbook: str | Path,
    *,
    场景名: str,
    次数: int = 1,
    seed: int = 0,
    world: 世界数据 | None = None,
    期望模式: bool = False,
    收集sample: bool = True,
    mode: str = "mc",
) -> dict[str, Any]:
    """技能 DES 批跑。

    mode:
      - mc: 仅真实蒙特卡洛（默认战斗路径）
      - ev: 仅期望模式分析（不替代真实战斗）
      - both: MC 为主 + 附带 1 次 EV 对照
    """
    w = world or 加载世界(workbook, 加载技能效果=True)
    mode = (mode or "mc").lower().strip()
    if 场景名 == "_smoke_" or not 场景名:
        auto = 默认木桩场景名(w.场景)
        if auto:
            场景名 = auto
        else:
            from ssot.金标命中 import 金标木桩基础伤害

            return 跑蒙特卡洛桩(
                workbook,
                场景名="_smoke_",
                次数=次数,
                world=w,
                基础伤害=float(金标木桩基础伤害(workbook)),
            )

    out: dict[str, Any] = {
        "场景": 场景名,
        "表名数": len(w.表名列表),
        "场景数": len(w.场景),
        "mode": mode,
    }

    if mode in ("mc", "both"):
        # 主路径强制 MC：忽略传入 期望模式
        mc = _跑一轮场景(
            w,
            场景名=场景名,
            次数=次数,
            seed=seed,
            期望模式=False,
            收集sample=收集sample,
        )
        out["mc"] = mc
        # 顶层兼容字段 = MC
        out.update(
            {
                "次数": 次数,
                "seed": mc["seed"],
                "攻方构筑": mc["攻方构筑"],
                "守方构筑": mc["守方构筑"],
                "战斗时长秒": mc["战斗时长秒"],
                "DPS": mc["DPS"]["mean"],
                "HPS": mc["HPS"]["mean"],
                "伤害总量": mc["伤害总量"]["mean"],
                "TTK": mc["TTK"]["mean"],
                "事件数": mc["事件数"]["mean"],
                "技能伤害占比": mc["技能伤害占比"],
                "sample": mc.get("sample") or [],
                "metrics": mc["metrics"],
            }
        )

    if mode in ("ev", "both"):
        ev_runs = 1 if mode == "both" else max(1, 次数)
        ev = _跑一轮场景(
            w,
            场景名=场景名,
            次数=ev_runs,
            seed=seed,
            期望模式=True,
            收集sample=(mode == "ev"),
        )
        out["ev"] = ev
        if mode == "ev":
            out.update(
                {
                    "次数": ev_runs,
                    "seed": ev["seed"],
                    "攻方构筑": ev["攻方构筑"],
                    "守方构筑": ev["守方构筑"],
                    "战斗时长秒": ev["战斗时长秒"],
                    "DPS": ev["DPS"]["mean"],
                    "HPS": ev["HPS"]["mean"],
                    "伤害总量": ev["伤害总量"]["mean"],
                    "TTK": ev["TTK"]["mean"],
                    "事件数": ev["事件数"]["mean"],
                    "技能伤害占比": ev["技能伤害占比"],
                    "sample": ev.get("sample") or [],
                    "metrics": ev["metrics"],
                }
            )

    return out




def 蒙特卡洛(
    场景: str | dict[str, Any] | None = None,
    n: int = 10,
    seed: int = 0,
    *,
    workbook: str | Path | None = None,
    world: 世界数据 | None = None,
    制图: bool = True,
    输出目录: str | Path | None = None,
) -> dict[str, Any]:
    """主路径 MC 批跑；写回用此结果。场景可为场景名或合成 dict。"""
    if isinstance(场景, dict) or 场景 is None or 场景 == "_synthetic_":
        out = _合成蒙特卡洛(场景 if isinstance(场景, dict) else None, n=n, seed=seed)
    else:
        if workbook is None:
            cand = Path("/workspace/combat-framework/战斗数值框架.xlsx")
            workbook = cand if cand.is_file() else Path(".")
        out = 跑场景战斗(
            workbook,
            场景名=str(场景),
            次数=n,
            seed=seed,
            world=world,
            mode="mc",
            收集sample=False,
        )
        # 归一化 runs 字段
        runs = (out.get("mc") or out).get("runs") or out.get("metrics", {}).get("samples") or []
        out["runs"] = runs
        from 战斗模拟.分析.方差汇总 import 方差汇总

        out["方差"] = 方差汇总(runs, 字段=("DPS", "HPS", "TTK"))

    if 制图:
        from 战斗模拟.报告.制图 import 绘制多指标

        runs = out.get("runs") or []
        charts = 绘制多指标(
            runs,
            字段列表=("DPS", "HPS", "TTK"),
            输出目录=输出目录,
            前缀=f"mc_s{seed}",
        )
        out["图表"] = charts
    return out


def 期望对照(
    场景: str | dict[str, Any] | None = None,
    n: int = 1,
    seed: int = 0,
    *,
    workbook: str | Path | None = None,
    world: 世界数据 | None = None,
) -> dict[str, Any]:
    """副路径 EV：管道期望模式 / 确定性中点；不替代 MC 写回。"""
    if isinstance(场景, dict) or 场景 is None or 场景 == "_synthetic_":
        out = _合成蒙特卡洛(
            场景 if isinstance(场景, dict) else None,
            n=max(1, n),
            seed=seed,
            期望模式=True,
        )
        out["路径"] = "EV"
        return out
    if workbook is None:
        cand = Path("/workspace/combat-framework/战斗数值框架.xlsx")
        workbook = cand if cand.is_file() else Path(".")
    out = 跑场景战斗(
        workbook,
        场景名=str(场景),
        次数=max(1, n),
        seed=seed,
        world=world,
        mode="ev",
        收集sample=False,
    )
    runs = (out.get("ev") or out).get("runs") or []
    out["runs"] = runs
    from 战斗模拟.分析.方差汇总 import 方差汇总

    out["方差"] = 方差汇总(runs, 字段=("DPS", "HPS", "TTK"))
    out["路径"] = "EV"
    return out


def 跑一场(
    *,
    workbook: str | Path | None = None,
    场景名: str,
    seed: int | None = None,
    期望模式: bool = False,
) -> dict[str, Any]:
    """真实场景单场：时长/种子/构筑只来自场景配置。"""
    from ssot import 框架路径

    path = Path(workbook) if workbook else 框架路径()
    w = 加载世界(path, 加载技能效果=True)
    sc = 取场景(w.场景, 场景名)
    if seed is None and sc.复现种子 is None:
        raise 数据缺失错误(f"场景 {场景名} 无复现种子")
    base_seed = int(seed if seed is not None else sc.复现种子)
    return _跑一轮场景(
        w,
        场景名=场景名,
        次数=1,
        seed=base_seed,
        期望模式=期望模式,
        收集sample=True,
    )


def _合成单场(*args, **kwargs):
    raise 数据缺失错误('合成单场已废除：生命/GCD/暴击不得硬编码，请走场景配置+技能战斗引擎')


def _合成蒙特卡洛(*args, **kwargs):
    raise 数据缺失错误('合成蒙特卡洛已废除：必须从框架簿场景批跑')


run_sim_batch = 跑蒙特卡洛桩
run_scene_combat = 跑场景战斗
monte_carlo = 蒙特卡洛
expectation_control = 期望对照
run_one_fight = 跑一场
