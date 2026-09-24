"""DES 事件与最小堆调度器（SimC 级事件种类）。"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class 事件种类(StrEnum):
    心跳 = "TICK"
    GCD就绪 = "GCD_READY"
    施法开始 = "CAST_START"
    施法完成 = "CAST_COMPLETE"
    引导跳 = "CHANNEL_TICK"
    命中 = "IMPACT"
    持续伤害跳 = "DOT_TICK"
    持续治疗跳 = "HOT_TICK"
    光环施加 = "AURA_APPLY"
    光环刷新 = "AURA_REFRESH"
    光环叠层 = "AURA_STACK"
    光环到期 = "AURA_EXPIRE"
    光环衰减 = "AURA_DECAY"
    触发 = "PROC"
    驱散 = "DISPEL"
    护盾破碎 = "SHIELD_BREAK"
    死亡 = "DEATH"
    时间轴 = "TIMELINE"
    移动 = "MOVE"
    自定义 = "CUSTOM"
    # 兼容旧引擎
    提交施法 = "COMMIT_CAST"


# 兼容旧英文 kind 字符串 / KIND_* 别名
KIND_TICK = 事件种类.心跳.value
KIND_GCD_READY = 事件种类.GCD就绪.value
KIND_CAST_START = 事件种类.施法开始.value
KIND_CAST_COMPLETE = 事件种类.施法完成.value
KIND_CHANNEL_TICK = 事件种类.引导跳.value
KIND_IMPACT = 事件种类.命中.value
KIND_DOT_TICK = 事件种类.持续伤害跳.value
KIND_HOT_TICK = 事件种类.持续治疗跳.value
KIND_AURA_APPLY = 事件种类.光环施加.value
KIND_AURA_REFRESH = 事件种类.光环刷新.value
KIND_AURA_STACK = 事件种类.光环叠层.value
KIND_AURA_EXPIRE = 事件种类.光环到期.value
KIND_AURA_DECAY = 事件种类.光环衰减.value
KIND_PROC = 事件种类.触发.value
KIND_DISPEL = 事件种类.驱散.value
KIND_SHIELD_BREAK = 事件种类.护盾破碎.value
KIND_DEATH = 事件种类.死亡.value
KIND_TIMELINE = 事件种类.时间轴.value
KIND_MOVE = 事件种类.移动.value
KIND_CUSTOM = 事件种类.自定义.value
KIND_COMMIT_CAST = 事件种类.提交施法.value


def 规范化事件种类(kind: str | 事件种类 | None) -> str:
    """把中文枚举名 / 英文值都收成 事件种类.value；空则空串。"""
    if kind is None:
        return ""
    if isinstance(kind, 事件种类):
        return kind.value
    s = str(kind).strip()
    if not s:
        return ""
    for item in 事件种类:
        if s == item.value or s == item.name:
            return item.value
    return s


@dataclass(order=True)
class 事件:
    时间毫秒: float
    序号: int
    种类: str = field(compare=False)
    载荷: dict[str, Any] = field(default_factory=dict, compare=False)
    已取消: bool = field(default=False, compare=False)

    @property
    def time_ms(self) -> float:
        return self.时间毫秒

    @property
    def seq(self) -> int:
        return self.序号

    @property
    def kind(self) -> str:
        return self.种类

    @property
    def payload(self) -> dict[str, Any]:
        return self.载荷


class 事件调度器:
    """真实 min-heap：schedule / cancel / advance / cancel_by_predicate。"""

    def __init__(self) -> None:
        self._heap: list[事件] = []
        self._seq = 0
        self.现在毫秒: float = 0.0
        self._id_index: dict[int, 事件] = {}

    @property
    def now(self) -> float:
        return self.现在毫秒

    @property
    def 队列长度(self) -> int:
        return sum(1 for e in self._heap if not e.已取消)

    def 调度(
        self,
        时间毫秒: float,
        种类: str,
        载荷: dict[str, Any] | None = None,
    ) -> int:
        self._seq += 1
        ev = 事件(float(时间毫秒), self._seq, str(种类), dict(载荷 or {}))
        heapq.heappush(self._heap, ev)
        self._id_index[self._seq] = ev
        return self._seq

    def 取消(self, 事件号: int) -> bool:
        ev = self._id_index.get(事件号)
        if ev is None or ev.已取消:
            return False
        ev.已取消 = True
        return True

    def 按条件取消(self, 谓词: Callable[[事件], bool]) -> int:
        """取消所有满足谓词且尚未弹出的事件；返回取消数量。"""
        n = 0
        for ev in list(self._id_index.values()):
            if ev.已取消:
                continue
            try:
                hit = bool(谓词(ev))
            except Exception:
                hit = False
            if hit:
                ev.已取消 = True
                n += 1
        return n

    def 推进(self) -> 事件 | None:
        """弹出下一个未取消事件并推进时钟；空则 None。"""
        while self._heap:
            ev = heapq.heappop(self._heap)
            self._id_index.pop(ev.序号, None)
            if ev.已取消:
                continue
            self.现在毫秒 = float(ev.时间毫秒)
            return ev
        return None

    def 清空(self) -> None:
        self._heap.clear()
        self._id_index.clear()
        self._seq = 0
        self.现在毫秒 = 0.0

    # 英文别名
    schedule = 调度
    cancel = 取消
    advance = 推进
    clear = 清空
    cancel_by_predicate = 按条件取消


Event = 事件
EventScheduler = 事件调度器
EventKind = 事件种类
