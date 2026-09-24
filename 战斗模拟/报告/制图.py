"""MC 方差制图：直方图 + 箱线图 PNG。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

_DEFAULT_OUT = Path("/workspace/数值工具/战斗模拟/报告/产出")


def _extract(样本: Sequence[Any], 字段: str) -> list[float]:
    out: list[float] = []
    for row in 样本:
        if isinstance(row, Mapping):
            v = row.get(字段)
        else:
            v = row
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def 绘制方差图(
    样本列表: Sequence[Any],
    *,
    字段: str = "DPS",
    标题: str | None = None,
    输出目录: str | Path | None = None,
    前缀: str = "mc",
) -> dict[str, str]:
    """生成 histogram + boxplot PNG，返回路径字典。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(输出目录) if 输出目录 else _DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    xs = _extract(样本列表, 字段)
    title = 标题 or f"{字段} distribution"
    paths: dict[str, str] = {}

    # histogram
    fig, ax = plt.subplots(figsize=(7, 4))
    if xs:
        ax.hist(xs, bins=min(20, max(5, len(xs))), color="#4C78A8", edgecolor="white", alpha=0.9)
        ax.axvline(sum(xs) / len(xs), color="#E45756", linestyle="--", label="mean")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "无样本", ha="center", va="center", transform=ax.transAxes)
    ax.set_title(f"{title} histogram")
    ax.set_xlabel(字段)
    ax.set_ylabel("count")
    hist_path = out_dir / f"{前缀}_{字段}_hist.png"
    fig.tight_layout()
    fig.savefig(hist_path, dpi=120)
    plt.close(fig)
    paths["histogram"] = str(hist_path)

    # boxplot
    fig2, ax2 = plt.subplots(figsize=(4, 5))
    if xs:
        ax2.boxplot(xs, orientation="vertical", patch_artist=True, boxprops=dict(facecolor="#72B7B2"))
    ax2.set_title(f"{title} boxplot")
    ax2.set_ylabel(字段)
    ax2.set_xticks([1], labels=[字段])
    box_path = out_dir / f"{前缀}_{字段}_box.png"
    fig2.tight_layout()
    fig2.savefig(box_path, dpi=120)
    plt.close(fig2)
    paths["boxplot"] = str(box_path)
    return paths


def 绘制多指标(
    样本列表: Sequence[Any],
    *,
    字段列表: Sequence[str] = ("DPS", "HPS", "TTK"),
    输出目录: str | Path | None = None,
    前缀: str = "mc",
) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for f in 字段列表:
        xs = _extract(样本列表, f)
        if not xs:
            continue
        out[f] = 绘制方差图(样本列表, 字段=f, 输出目录=输出目录, 前缀=前缀)
    return out


# 英文别名
plot_variance = 绘制方差图
plot_metrics = 绘制多指标
