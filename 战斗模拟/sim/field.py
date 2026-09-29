"""数值档场地：圆内站位，比较距离后决定走近还是出手。"""
from __future__ import annotations

import math


class Field:
    def __init__(self, radius: float, gap: float):
        if not radius or not gap:
            raise ValueError("场地半径和距中线必须来自场景或模拟参数")
        self.radius = radius
        self.gap = gap
        self.pos: dict[str, tuple[float, float]] = {}

    def place(self, units: list[dict]) -> None:
        groups = {"A": [], "B": []}
        for unit in units:
            groups.get(unit["阵营"], groups["A"]).append(unit)
        for side, members in groups.items():
            sign = -1 if side == "A" else 1
            for index, unit in enumerate(members):
                y = (index - (len(members) - 1) / 2) * 2.5
                x = sign * self.gap
                self.pos[unit["名称"]] = (x, y)

    def distance(self, a: str, b: str) -> float:
        ax, ay = self.pos[a]
        bx, by = self.pos[b]
        return math.hypot(ax - bx, ay - by)

    def move_toward(self, name: str, other: str, meters: float) -> float:
        ax, ay = self.pos[name]
        bx, by = self.pos[other]
        dist = math.hypot(ax - bx, ay - by)
        if dist <= 0.05 or meters <= 0:
            return dist
        step = min(meters, dist)
        self.pos[name] = (ax + (bx - ax) / dist * step, ay + (by - ay) / dist * step)
        return self.distance(name, other)

    def move_away(self, name: str, other: str, meters: float) -> None:
        ax, ay = self.pos[name]
        bx, by = self.pos[other]
        dist = math.hypot(ax - bx, ay - by) or 0.05
        nx = ax + (ax - bx) / dist * meters
        ny = ay + (ay - by) / dist * meters
        limit = self.radius - 0.5
        scale = max(abs(nx), abs(ny), 0.01)
        if scale > limit:
            nx *= limit / scale
            ny *= limit / scale
        self.pos[name] = (nx, ny)
