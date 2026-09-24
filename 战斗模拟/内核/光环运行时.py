"""光环运行时：挂载 / 快照 / 层衰减 / 驱散与偷取。

效果总表叠层规则已在「效果事件*」管线分支算好层数与时长；本模块负责真正写入实体
光环表，并提供驱散选取、转移、衰减与跳动面板解析。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Iterable


_空互斥 = frozenset({"", "空", "无", "none", "None"})
_真值 = frozenset({"是", "true", "True", "1", "Y", "y", "yes", "YES"})


def _是真(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip() in _真值


def _互斥有效(组: Any) -> bool:
    s = str(组 or "").strip()
    return bool(s) and s not in _空互斥


def 解析快照属性列表(原文: Any) -> list[str]:
    """分号 / 逗号 / 顿号 / 斜杠分隔；空 → []（表示全面板）。"""
    if 原文 is None:
        return []
    if isinstance(原文, (list, tuple)):
        return [str(x).strip() for x in 原文 if str(x).strip()]
    s = str(原文).strip()
    if not s or s in ("全面板", "*", "全部", "空", "无"):
        return []
    for sep in (";", "；", ",", "，", "、", "/", "|"):
        s = s.replace(sep, ";")
    return [p.strip() for p in s.split(";") if p.strip()]


def _面板字典(panel: dict[str, Any] | None) -> dict[str, Any]:
    if not panel:
        return {}
    nested = panel.get("面板") if isinstance(panel.get("面板"), dict) else None
    out: dict[str, Any] = {}
    if nested:
        out.update(nested)
    for k, v in panel.items():
        if k in ("面板", "护盾层", "光环列表", "状态", "标记", "标签", "_实体"):
            continue
        out[k] = v
    return out


@dataclass
class 光环实例:
    效果代号: str
    层数: int = 1
    剩余时长: float = 0.0
    快照: dict[str, Any] = field(default_factory=dict)
    衰减间隔: float = 0.0
    衰减数量: int = 0
    驱散类型: str = "可驱散"  # 可驱散 / 仅强驱 / 不可驱散（效果总表「驱散类型」）
    可窃取: bool = False
    互斥组: str = "空"
    标签: str = ""
    来源id: str = ""
    快照时机: str = "无"
    跳动间隔: float = 0.0
    数值类型: str = "无"
    到期动作: str = ""
    驱散优先级: int = 0
    首领抗性: float = 0.0
    效果类型: str = "减益"
    最大层数: int = 1
    叠加规则: str = "刷新"
    uid: int = 0
    # 调度句柄（引擎写入，取消时用）
    到期事件号: int | None = None
    衰减事件号: int | None = None
    跳动事件号: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | "光环实例") -> "光环实例":
        if isinstance(d, 光环实例):
            return d
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in dict(d).items() if k in known}
        if "可窃取" in kwargs:
            kwargs["可窃取"] = _是真(kwargs["可窃取"])
        for int_k in ("层数", "衰减数量", "驱散优先级", "最大层数", "uid"):
            if int_k in kwargs and kwargs[int_k] is not None:
                try:
                    kwargs[int_k] = int(float(kwargs[int_k]))
                except (TypeError, ValueError):
                    pass
        for fl_k in ("剩余时长", "衰减间隔", "跳动间隔", "首领抗性"):
            if fl_k in kwargs and kwargs[fl_k] is not None:
                try:
                    kwargs[fl_k] = float(kwargs[fl_k])
                except (TypeError, ValueError):
                    pass
        if "快照" in kwargs and not isinstance(kwargs["快照"], dict):
            kwargs["快照"] = {}
        return cls(**kwargs)


_UID_SEQ = 0


def _next_uid() -> int:
    global _UID_SEQ
    _UID_SEQ += 1
    return _UID_SEQ


def 取光环列表(side: dict[str, Any] | None) -> list[光环实例]:
    """取得 side 上的光环列表（就地 list，元素规范为 光环实例）。"""
    if not isinstance(side, dict):
        return []
    raw = side.get("光环列表")
    if raw is None:
        # 兼容实体挂在 _实体
        ent = side.get("_实体")
        if ent is not None and hasattr(ent, "光环列表"):
            raw = getattr(ent, "光环列表")
            side["光环列表"] = raw
    if not isinstance(raw, list):
        raw = []
        side["光环列表"] = raw
    # 规范化：dict → 光环实例（就地替换以便后续写回）
    for i, item in enumerate(raw):
        if not isinstance(item, 光环实例):
            raw[i] = 光环实例.from_dict(item if isinstance(item, dict) else {"效果代号": str(item)})
    return raw  # type: ignore[return-value]


def 同步光环到实体(side: dict[str, Any] | None) -> None:
    """若 side 带 _实体，把光环列表写回实体字段。"""
    if not isinstance(side, dict):
        return
    ent = side.get("_实体")
    if ent is None:
        return
    auras = 取光环列表(side)
    try:
        ent.光环列表 = list(auras)
    except Exception:
        try:
            setattr(ent, "光环列表", list(auras))
        except Exception:
            pass


def 查找同效果(side: dict[str, Any] | None, 效果代号: str) -> list[光环实例]:
    code = str(效果代号 or "").strip()
    if not code:
        return []
    return [a for a in 取光环列表(side) if a.效果代号 == code]


def 有同效果(side: dict[str, Any] | None, 效果代号: str) -> bool:
    return bool(查找同效果(side, 效果代号))


def 互斥组冲突(side: dict[str, Any] | None, 互斥组: Any) -> bool:
    if not _互斥有效(互斥组):
        return False
    g = str(互斥组).strip()
    return any(str(a.互斥组).strip() == g for a in 取光环列表(side))


def 移除同效果(side: dict[str, Any] | None, 效果代号: str) -> list[光环实例]:
    code = str(效果代号 or "").strip()
    auras = 取光环列表(side)
    kept: list[光环实例] = []
    removed: list[光环实例] = []
    for a in auras:
        if a.效果代号 == code:
            removed.append(a)
        else:
            kept.append(a)
    auras[:] = kept
    同步光环到实体(side)
    return removed


def 移除互斥组效果(side: dict[str, Any] | None, 互斥组: Any) -> list[光环实例]:
    if not _互斥有效(互斥组):
        return []
    g = str(互斥组).strip()
    auras = 取光环列表(side)
    kept: list[光环实例] = []
    removed: list[光环实例] = []
    for a in auras:
        if str(a.互斥组).strip() == g:
            removed.append(a)
        else:
            kept.append(a)
    auras[:] = kept
    同步光环到实体(side)
    return removed


def 移除效果(
    side: dict[str, Any] | None,
    效果代号: str = "",
    *,
    uid: int | None = None,
) -> list[光环实例]:
    auras = 取光环列表(side)
    code = str(效果代号 or "").strip()
    kept: list[光环实例] = []
    removed: list[光环实例] = []
    for a in auras:
        hit = False
        if uid is not None and a.uid == int(uid):
            hit = True
        elif code and a.效果代号 == code and uid is None:
            hit = True
        if hit:
            removed.append(a)
        else:
            kept.append(a)
    auras[:] = kept
    同步光环到实体(side)
    return removed


def 按uid移除(side: dict[str, Any] | None, uid: int) -> 光环实例 | None:
    removed = 移除效果(side, uid=int(uid))
    return removed[0] if removed else None


def _从上下文建实例(ctx: dict[str, Any], 效果代号: str, 层数: int, 剩余时长: float) -> 光环实例:
    # 效果总表「驱散类型」列 = 可驱散/仅强驱/不可驱散；管线驱散时「驱散类型」=通道
    raw_tier = str(ctx.get("驱散类型等级") or "").strip()
    raw_disp = str(ctx.get("驱散类型") or "").strip()
    if raw_tier in ("可驱散", "仅强驱", "不可驱散"):
        tier = raw_tier
    elif raw_disp in ("可驱散", "仅强驱", "不可驱散"):
        tier = raw_disp
    else:
        tier = "可驱散"
    try:
        prio = int(float(ctx.get("驱散优先级") or 0))
    except (TypeError, ValueError):
        prio = 0
    try:
        max_stacks = int(float(ctx.get("最大层数") or 1))
    except (TypeError, ValueError):
        max_stacks = 1
    steal_raw = ctx.get("可窃取")
    if steal_raw is None:
        steal_raw = ctx.get("可窃取/转移")
    return 光环实例(
        效果代号=str(效果代号),
        层数=max(0, int(层数)),
        剩余时长=float(剩余时长),
        衰减间隔=float(ctx.get("层衰减间隔") or 0.0),
        衰减数量=int(float(ctx.get("层衰减数量") or 0)),
        驱散类型=tier,
        可窃取=_是真(steal_raw),
        互斥组=str(ctx.get("互斥组") or "空"),
        标签=str(ctx.get("标签") or ""),
        来源id=str((ctx.get("攻方") or {}).get("id") or ctx.get("来源id") or ""),
        快照时机=str(ctx.get("快照时机") or "无"),
        跳动间隔=float(ctx.get("跳动间隔") or 0.0),
        数值类型=str(ctx.get("数值类型") or "无"),
        到期动作=str(ctx.get("到期动作") or ""),
        驱散优先级=prio,
        首领抗性=float(ctx.get("首领抗性") or 0.0),
        效果类型=str(ctx.get("效果类型") or "减益"),
        最大层数=max(1, max_stacks),
        叠加规则=str(ctx.get("叠加规则") or "刷新"),
        uid=_next_uid(),
        快照={},
    )


def 挂载效果(
    side: dict[str, Any] | None,
    效果代号: str,
    层数: int | float,
    剩余时长: float,
    *,
    ctx: dict[str, Any] | None = None,
    叠加规则: str | None = None,
) -> 光环实例:
    """按管线已算好的层数/时长写入；独立=并列，其余同代号则更新首个实例。"""
    ctx = ctx or {}
    rule = str(叠加规则 or ctx.get("叠加规则") or "刷新").strip() or "刷新"
    code = str(效果代号 or ctx.get("效果代号") or "").strip()
    if not code:
        raise ValueError("挂载效果需要效果代号")
    stacks = int(float(层数))
    dur = float(剩余时长)
    auras = 取光环列表(side)
    existing = [a for a in auras if a.效果代号 == code]

    if rule == "独立" or not existing:
        inst = _从上下文建实例(ctx, code, stacks, dur)
        auras.append(inst)
        同步光环到实体(side)
        return inst

    # 非独立：更新第一个同代号实例（管线已处理取强/取弱/替换分支）
    inst = existing[0]
    inst.层数 = max(0, stacks)
    inst.剩余时长 = dur
    inst.衰减间隔 = float(ctx.get("层衰减间隔") or inst.衰减间隔)
    inst.衰减数量 = int(float(ctx.get("层衰减数量") or inst.衰减数量))
    inst.跳动间隔 = float(ctx.get("跳动间隔") or inst.跳动间隔)
    inst.快照时机 = str(ctx.get("快照时机") or inst.快照时机)
    inst.叠加规则 = rule
    if ctx.get("标签") not in (None, ""):
        inst.标签 = str(ctx.get("标签"))
    if ctx.get("到期动作") not in (None, ""):
        inst.到期动作 = str(ctx.get("到期动作"))
    steal_raw = ctx.get("可窃取")
    if steal_raw is None:
        steal_raw = ctx.get("可窃取/转移")
    if steal_raw is not None:
        inst.可窃取 = _是真(steal_raw)
    tier = ctx.get("驱散类型等级") or ctx.get("驱散类型")
    if tier and str(tier) in ("可驱散", "仅强驱", "不可驱散"):
        inst.驱散类型 = str(tier)
    同步光环到实体(side)
    return inst


def 写入快照(
    aura: 光环实例,
    来源面板: dict[str, Any] | None,
    快照属性列表: Any = None,
) -> dict[str, Any]:
    """若调用方已判定快照时机==施加时，将攻方面板属性拷入 aura.snapshot。"""
    panel = _面板字典(来源面板)
    keys = 解析快照属性列表(快照属性列表)
    if not keys:
        snap = dict(panel)
    else:
        snap = {k: panel.get(k) for k in keys if k in panel}
        # 列表里有但面板缺的键仍占位为 None，便于测试断言「冻结集合」
        for k in keys:
            if k not in snap:
                snap[k] = panel.get(k)
    aura.快照 = snap
    return snap


def 衰减层数(
    side: dict[str, Any] | None,
    aura: 光环实例 | None = None,
    *,
    效果代号: str = "",
    uid: int | None = None,
    数量: int | None = None,
) -> tuple[光环实例 | None, bool]:
    """减层；层数≤0 则移除。返回 (实例或None, 是否已移除)。"""
    auras = 取光环列表(side)
    target: 光环实例 | None = aura
    if target is None:
        if uid is not None:
            for a in auras:
                if a.uid == int(uid):
                    target = a
                    break
        elif 效果代号:
            found = 查找同效果(side, 效果代号)
            target = found[0] if found else None
    if target is None:
        return None, False
    n = int(数量) if 数量 is not None else int(target.衰减数量 or 0)
    if n <= 0:
        n = 1
    target.层数 = int(target.层数) - n
    if target.层数 <= 0:
        按uid移除(side, target.uid)
        return target, True
    同步光环到实体(side)
    return target, False


def 可驱散列表(
    side: dict[str, Any] | None,
    *,
    已尝试uids: Iterable[int] | None = None,
    含不可驱散: bool = True,
) -> list[光环实例]:
    tried = set(int(x) for x in (已尝试uids or []))
    out: list[光环实例] = []
    for a in 取光环列表(side):
        if a.uid in tried:
            continue
        if not 含不可驱散 and a.驱散类型 == "不可驱散":
            continue
        out.append(a)
    out.sort(key=lambda x: (-int(x.驱散优先级), x.uid))
    return out


def 有可驱散效果(
    side: dict[str, Any] | None,
    *,
    已尝试uids: Iterable[int] | None = None,
) -> bool:
    return bool(可驱散列表(side, 已尝试uids=已尝试uids, 含不可驱散=True))


def 选取可驱散效果(
    side: dict[str, Any] | None,
    *,
    已尝试uids: Iterable[int] | None = None,
) -> 光环实例 | None:
    cands = 可驱散列表(side, 已尝试uids=已尝试uids, 含不可驱散=True)
    return cands[0] if cands else None


def 匹配驱散类型(光环标签: Any, 技能驱散类型: Any) -> bool:
    """技能驱散通道 vs 光环标签。空/无 → 通配。"""
    skill = str(技能驱散类型 or "").strip()
    tag = str(光环标签 or "").strip()
    if not skill or skill in ("无", "全部", "*", "空"):
        return True
    if not tag or tag in ("无", "空"):
        return True
    # 多选标签：魔法/诅咒
    parts = []
    for sep in ("/", ";", "；", ",", "，", "|"):
        if sep in tag:
            parts = [p.strip() for p in tag.replace("；", ";").replace("，", ",").replace("/", ";").replace("|", ";").replace(",", ";").split(";") if p.strip()]
            break
    if not parts:
        parts = [tag]
    return skill in parts or tag == skill


def 填充上下文自光环(ctx: dict[str, Any], aura: 光环实例) -> None:
    """选取后把光环字段灌进管线上下文，供后续判定使用。"""
    ctx["效果代号"] = aura.效果代号
    ctx["标签"] = aura.标签
    ctx["驱散类型等级"] = aura.驱散类型
    # 保留技能驱散通道在 驱散类型；若未被设过则不动
    ctx["可窃取"] = "是" if aura.可窃取 else "否"
    ctx["到期动作"] = aura.到期动作
    ctx["首领抗性"] = float(aura.首领抗性)
    ctx["异常层数"] = float(aura.层数)
    ctx["当前层数"] = float(aura.层数)
    ctx["剩余时长"] = float(aura.剩余时长)
    ctx["互斥组"] = aura.互斥组
    ctx["效果类型"] = aura.效果类型
    ctx["_当前光环uid"] = aura.uid
    ctx["_当前光环"] = aura


def 转移效果(
    源: dict[str, Any] | None,
    目标: dict[str, Any] | None,
    效果代号: str = "",
    *,
    uid: int | None = None,
) -> 光环实例 | None:
    """从源移除并挂到目标（偷取）。"""
    removed: list[光环实例]
    if uid is not None:
        inst = 按uid移除(源, int(uid))
        removed = [inst] if inst else []
    else:
        removed = 移除效果(源, 效果代号)
    if not removed:
        return None
    inst = removed[0]
    # 偷取后仍保留快照与层数；来源改为新持有者侧由调用方决定
    dst = 取光环列表(目标)
    dst.append(inst)
    同步光环到实体(目标)
    同步光环到实体(源)
    return inst


def 跳动属性面板(
    aura: 光环实例,
    来源面板: dict[str, Any] | None,
) -> dict[str, Any]:
    """快照时机==施加时 → 用冻结快照；否则动态面板。"""
    if str(aura.快照时机 or "") == "施加时" and aura.快照:
        return dict(aura.快照)
    return _面板字典(来源面板)


def 取消光环调度(调度器: Any, aura: 光环实例) -> None:
    if 调度器 is None:
        return
    for eid in (aura.到期事件号, aura.衰减事件号, aura.跳动事件号):
        if eid is not None:
            try:
                调度器.取消(int(eid))
            except Exception:
                pass
    aura.到期事件号 = None
    aura.衰减事件号 = None
    aura.跳动事件号 = None


# 英文别名
AuraInstance = 光环实例
