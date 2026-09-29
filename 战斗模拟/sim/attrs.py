"""战斗中的属性。开场快照之后只在内存里加减，不再读表。"""
from __future__ import annotations


class AttrBag:
    def __init__(self, base: dict[str, float]):
        self.base = {k: float(v) for k, v in base.items()}
        self.added: dict[str, float] = {}
        self.factor: dict[str, float] = {}

    def get(self, name: str) -> float:
        value = self.base.get(name, 0.0) + self.added.get(name, 0.0)
        return value * self.factor.get(name, 1.0)

    def as_dict(self) -> dict[str, float]:
        names = set(self.base) | set(self.added) | set(self.factor)
        return {name: self.get(name) for name in names}

    def apply(self, name: str, op: str, value: float) -> None:
        if op == "加":
            self.added[name] = self.added.get(name, 0.0) + value
        elif op == "乘":
            self.factor[name] = self.factor.get(name, 1.0) * value
        elif op in ("覆盖", "设"):
            self.base[name] = value
            self.added[name] = 0.0
            self.factor[name] = 1.0

    def revert(self, name: str, op: str, value: float) -> None:
        if op == "加":
            self.added[name] = self.added.get(name, 0.0) - value
        elif op == "乘" and value:
            self.factor[name] = self.factor.get(name, 1.0) / value
        elif op in ("覆盖", "设"):
            pass
