"""结构化战斗日志：JSONL + 可选简要文本。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class 日志条目:
    时间毫秒: float
    事件种类: str
    攻方id: str = ""
    守方id: str = ""
    技能或效果: str = ""
    结果: dict[str, Any] = field(default_factory=dict)
    随机种子位点: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d["随机种子位点"] is None:
            d.pop("随机种子位点", None)
        return d

    def 简要(self) -> str:
        skill = self.技能或效果 or "-"
        res = self.结果 or {}
        keys = ("最终伤害", "实际扣血", "实际治疗", "异常挂载结果", "命中", "暴击")
        bits = []
        for k in keys:
            if k in res and res[k] is not None:
                bits.append(f"{k}={res[k]}")
        extra = (" ".join(bits)) if bits else json.dumps(res, ensure_ascii=False)[:120]
        return (
            f"t={self.时间毫秒:.1f}ms {self.事件种类} "
            f"{self.攻方id}->{self.守方id} [{skill}] {extra}"
        )


class 战斗日志:
    """对齐架构：时间 / 种类 / 攻守 / 技能效果 / 结果字典 / 可选 RNG 位点。"""

    def __init__(self) -> None:
        self._entries: list[日志条目] = []

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    @property
    def 条目(self) -> list[日志条目]:
        return list(self._entries)

    def append(
        self,
        时间毫秒: float,
        事件种类: str,
        攻方id: str = "",
        守方id: str = "",
        技能或效果: str = "",
        结果: dict[str, Any] | None = None,
        随机种子位点: int | None = None,
        *,
        技能: str | None = None,
        效果: str | None = None,
    ) -> 日志条目:
        label = 技能或效果 or 技能 or 效果 or ""
        entry = 日志条目(
            时间毫秒=float(时间毫秒),
            事件种类=str(事件种类),
            攻方id=str(攻方id or ""),
            守方id=str(守方id or ""),
            技能或效果=str(label),
            结果=dict(结果 or {}),
            随机种子位点=随机种子位点,
        )
        self._entries.append(entry)
        return entry

    def 清空(self) -> None:
        self._entries.clear()

    def export_jsonl(
        self,
        path: str | Path | None = None,
    ) -> str:
        lines = [
            json.dumps(e.to_dict(), ensure_ascii=False, default=str)
            for e in self._entries
        ]
        text = "\n".join(lines) + ("\n" if lines else "")
        if path is not None:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return text

    def export_text(self, path: str | Path | None = None) -> str:
        lines = [e.简要() for e in self._entries]
        text = "\n".join(lines) + ("\n" if lines else "")
        if path is not None:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return text

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._entries]

    def extend(self, entries: Iterable[日志条目 | dict[str, Any]]) -> None:
        for e in entries:
            if isinstance(e, 日志条目):
                self._entries.append(e)
            else:
                self.append(**e)  # type: ignore[arg-type]


CombatLog = 战斗日志
LogEntry = 日志条目
