"""场地只使用场景或模拟参数里写明的半径、间距、碰撞。缺了就记入待对齐。"""
from __future__ import annotations

import math


def _num(value):
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Arena:
    def __init__(self, scene: dict | None, params: dict, gaps: list[str]):
        scene = scene or {}
        self.radius = _num(scene.get("场地半径"))
        if self.radius is None:
            self.radius = _num(params.get("默认场地半径"))
        if self.radius is None:
            gaps.append("场景没有场地半径，模拟参数也没有默认场地半径")
        self.gap = _num(scene.get("A距中线"))
        if self.gap is None:
            self.gap = _num(scene.get("B距中线"))
        if self.gap is None:
            self.gap = _num(params.get("默认距中线"))
        if self.gap is None:
            gaps.append("场景没有距中线，模拟参数也没有默认距中线")
        self.spacing = {
            "A": _num(scene.get("A间距")),
            "B": _num(scene.get("B间距")),
        }
        for side, value in list(self.spacing.items()):
            if value is None:
                fallback = _num(params.get(f"默认{side}间距"))
                if fallback is None:
                    fallback = 1.5 if side == "A" else 1.0
                    text = f"场景没有{side}间距，模拟参数也没有默认{side}间距，临时用 {fallback}"
                else:
                    text = f"场景没有{side}间距，已用模拟参数默认{side}间距={fallback}"
                if text not in gaps:
                    gaps.append(text)
                self.spacing[side] = fallback
        self.collision = _num(scene.get("默认碰撞半径"))
        if self.collision is None:
            self.collision = _num(params.get("默认碰撞半径"))
        self.height = _num(scene.get("默认碰撞高度"))
        if self.height is None:
            self.height = _num(params.get("默认碰撞高度"))
        self.body = scene.get("默认受击体积")
        self.terrain = scene.get("地形")
        self.pos: dict[str, tuple[float, float]] = {}
        self.facing: dict[str, float] = {}
        if scene.get("场地长") or scene.get("场地宽") or scene.get("高度图"):
            text = "场景写了场地长宽或高度图，当前推进仍只用半径圆，这两列还没有参与碰撞"
            if text not in gaps:
                gaps.append(text)
    def place(self, units: list[dict], slots: list[dict] | None, scene_name: str) -> None:
        placed = {}
        for slot in slots or []:
            if str(slot.get("场景名") or "") != scene_name:
                continue
            name = str(slot.get("单位名") or "")
            x, y, z = _num(slot.get("出生X")), _num(slot.get("出生Y")), _num(slot.get("出生Z"))
            if name and x is not None and y is not None:
                placed[name] = (x, y if z is None else y)
        groups = {"A": [], "B": []}
        for unit in units:
            groups.get(unit["阵营"], groups["A"]).append(unit)
        for side, members in groups.items():
            sign = -1 if side == "A" else 1
            spacing = self.spacing.get(side)
            gap = self.gap or 0
            for index, unit in enumerate(members):
                if unit["名称"] in placed:
                    x, y = placed[unit["名称"]]
                else:
                    y = 0 if spacing is None else (index - (len(members) - 1) / 2) * spacing
                    x = sign * gap
                self.pos[unit["名称"]] = (x, y)
                self.facing[unit["名称"]] = 0 if side == "A" else math.pi

    def distance(self, a: str, b: str) -> float:
        ax, ay = self.pos[a]
        bx, by = self.pos[b]
        return math.hypot(ax - bx, ay - by)

    def move(self, name: str, other: str, meters: float, away: bool = False) -> None:
        ax, ay = self.pos[name]
        bx, by = self.pos[other]
        dist = math.hypot(bx - ax, by - ay) or 0.0001
        direction = -1 if away else 1
        step = meters * direction
        nx = ax + (bx - ax) / dist * step
        ny = ay + (by - ay) / dist * step
        if self.collision:
            limit = self.distance(name, other) - self.collision * 2
            if not away and meters > limit > 0:
                scale = limit / meters
                nx = ax + (nx - ax) * scale
                ny = ay + (ny - ay) * scale
        if self.radius:
            reach = math.hypot(nx, ny)
            if reach > self.radius:
                nx *= self.radius / reach
                ny *= self.radius / reach
        self.pos[name] = (nx, ny)
        self.facing[name] = math.atan2((by - ay) * direction, (bx - ax) * direction)

    def in_splash(self, origin: str, radius: float, camp: str, units: list[dict]) -> list[dict]:
        found = []
        for unit in units:
            if unit["阵营"] != camp or unit["生命值"] <= 0:
                continue
            if self.distance(origin, unit["名称"]) <= radius:
                found.append(unit)
        return found
