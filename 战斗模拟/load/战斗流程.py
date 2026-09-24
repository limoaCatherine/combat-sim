"""加载「战斗流程」横排管线块，供模拟器解析。

布局：每个管线占 6 列 + 1 空列（stride=7）；R1=表名，R2空，R3=管线名，R4=表头，R5起=步骤。
列：管线 | 步骤序 | 步骤名 | 判定公式 | 成功跳转 | 失败跳转

判定公式（中文标准 DSL）
-----------------------
「判定公式」列存放中文标准 DSL，例如：
``设管线伤害(基础伤害)``、``随机()<效果(闪避效果(PVE))``、``伤害类型==物理``。
属性取用 ``效果/攻方/守方`` 的用途名必须存在于「属性总表」列 B。
详见 ``战斗模拟/文档/战斗流程标准语法.md`` 与 ``领域/流程语法.py``。

跳转约定
--------
成功跳转 / 失败跳转 为整数：
- ``0`` = 顺序下一（同管线步骤序 + 1）
- ``>0`` = 跳到同管线该步骤序
- ``-1`` = 管线结束（pipeline end）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HEADERS = ("管线", "步骤序", "步骤名", "判定公式", "成功跳转", "失败跳转")
EVENT_HEADERS = ("事件种类", "进管线", "入口步骤", "来源覆盖", "备注", "启用")
EVENT_BLOCK = "事件接入"
EVENT_BLOCKS = frozenset({"结算入口", "事件目录", "事件接入"})
事件页 = "事件"
# 非管线块：同 stride 横排，但列义不同，加载器必须跳过，否则会当步骤序去 int。
META_BLOCKS = frozenset({
    EVENT_BLOCK,
    "结算入口",
    "事件目录",
    "管线目录",
    "流程参数",
})
COLS_PER_BLOCK = 6
BLOCK_STRIDE = 7  # 6 + 1 gap

TITLE_ROW = 3  # 管线名
HEADER_ROW = 4
DATA_START_ROW = 5


@dataclass(frozen=True)
class 流程步骤:
    管线: str
    步骤序: int
    步骤名: str
    判定公式: str  # 中文标准 DSL
    成功跳转: int
    失败跳转: int


@dataclass(frozen=True)
class 事件接入:
    种类: str
    进管线: str
    入口步骤: int
    来源覆盖: str
    备注: str
    启用: bool
    入口段名: str = ""


@dataclass(frozen=True)
class 流程阶段:
    路名: str
    第几段: int
    段名: str
    跳过条件: str
    判定公式: str
    调用机制: str
    写出结果: str
    适用: str
    启用: bool
    成功跳转: int = 0
    失败跳转: int = 0


PLAN_TITLE = "有哪些路"
PLAN_STAGE_TITLE = "各路按什么顺序判"
PLAN_EVENT_TITLE = "什么事件进哪条路"
PLAN_CATALOG_TITLE = "管线目录"
PLAN_MECH_TITLE = "机制阶段"
PLAN_PARAM_TITLE = "流程参数"
MECH_SHEET = "机制流程"
MECH_STAGE_TITLE = "各机制按什么顺序判"
对照页 = "战斗流程对照"
主路径块 = frozenset({
    "伤害",
    "治疗",
    "状态施加",
    "伤害PVE",
    "伤害PVP",
    "治疗PVE",
    "治疗PVP",
    "状态PVE",
    "状态PVP",
    "伤害环境",
    "伤害对战",
    "治疗环境",
    "治疗对战",
    "状态环境",
    "状态对战",
})

NEW_PIPE_ALIASES = {
    "伤害环境": "伤害PVE",
    "伤害对战": "伤害PVP",
    "治疗环境": "治疗PVE",
    "治疗对战": "治疗PVP",
    "状态环境": "状态PVE",
    "状态对战": "状态PVP",
    "状态施加": "状态PVE",
    "效果事件PVE": "状态PVE",
    "效果事件PVP": "状态PVP",
    "异常PVE": "状态PVE",
    "异常PVP": "状态PVP",
    "驱散PVE": "驱散与偷取",
    "驱散PVP": "驱散与偷取",
    "光环存续": "效果存续",
}

MODE_PIPE = {
    ("伤害", "PVE"): "伤害PVE",
    ("伤害", "PVP"): "伤害PVP",
    ("治疗", "PVE"): "治疗PVE",
    ("治疗", "PVP"): "治疗PVP",
    ("状态施加", "PVE"): "状态PVE",
    ("状态施加", "PVP"): "状态PVP",
}

事件名到种类 = {
    "直击命中": "IMPACT",
    "命中": "IMPACT",
    "持续伤害跳动": "DOT_TICK",
    "持续伤害跳": "DOT_TICK",
    "持续治疗跳动": "HOT_TICK",
    "持续治疗跳": "HOT_TICK",
    "效果施加": "AURA_APPLY",
    "光环施加": "AURA_APPLY",
    "效果刷新": "AURA_REFRESH",
    "光环刷新": "AURA_REFRESH",
    "效果叠层": "AURA_STACK",
    "光环叠层": "AURA_STACK",
    "效果层衰减": "AURA_DECAY",
    "光环衰减": "AURA_DECAY",
    "效果到期": "AURA_EXPIRE",
    "光环到期": "AURA_EXPIRE",
    "驱散请求": "DISPEL",
    "驱散": "DISPEL",
    "施法起手": "CAST_START",
    "施法开始": "CAST_START",
    "施法完成": "CAST_COMPLETE",
    "引导跳动": "CHANNEL_TICK",
    "引导跳": "CHANNEL_TICK",
    "公共冷却就绪": "GCD_READY",
    "效果触发": "PROC",
    "触发": "PROC",
    "护盾破碎": "SHIELD_BREAK",
    "单位死亡": "DEATH",
    "死亡": "DEATH",
    "仿真心跳": "TICK",
    "心跳": "TICK",
    "时间轴节点": "TIMELINE",
    "时间轴": "TIMELINE",
    "位移完成": "MOVE",
    "移动": "MOVE",
    "自定义派发": "CUSTOM",
    "自定义": "CUSTOM",
    "提交施法": "COMMIT_CAST",
}


class 战斗流程加载错误(ValueError):
    """战斗流程表结构或跳转约定不合法。"""


def _as_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    return int(v)


def _校验跳转(step: 流程步骤, orders: set[int]) -> 流程步骤:
    suc, fail = step.成功跳转, step.失败跳转
    # -1 = 管线结束；0 = 下一；>0 = 跳到步骤序
    allowed = {-1, 0} | orders
    for label, j in (("成功跳转", suc), ("失败跳转", fail)):
        if j not in allowed:
            raise 战斗流程加载错误(
                f"管线「{step.管线}」步骤序 {step.步骤序} 的{label}={j} "
                f"不在 {{-1,0}}∪{sorted(orders)}"
            )
    return step


def 加载战斗流程(
    wb,
    *,
    validate_jumps: bool = True,
) -> dict[str, list[流程步骤]]:
    """返回 {管线名: [步骤…]}，步骤按步骤序排序。

    Parameters
    ----------
    validate_jumps:
        校验跳转目标 ∈ {{-1, 0}} ∪ 本管线步骤序集合。
    """
    ws = wb["战斗流程"]
    if 是规划面(ws):
        if 对照页 in wb.sheetnames:
            ws = wb[对照页]
        else:
            return {}
    r2 = str(ws.cell(2, 1).value or "").strip()
    r3 = str(ws.cell(3, 1).value or "").strip()
    if r2 in {"伤害环境", "伤害PVE"} and r3 == "管线":
        title_row, data_start, stride = 2, 4, 6
    else:
        title_row, data_start, stride = TITLE_ROW, DATA_START_ROW, BLOCK_STRIDE
    out: dict[str, list[流程步骤]] = {}
    max_c = ws.max_column or 1
    bi = 0
    while True:
        c0 = 1 + bi * stride
        if c0 > max_c:
            break
        name = ws.cell(title_row, c0).value
        if not name:
            bi += 1
            if bi > 32:
                break
            continue
        name = str(name).strip()
        if name in META_BLOCKS or name in {"管线", "步骤序", "事件接入"}:
            bi += 1
            continue
        steps: list[流程步骤] = []
        for r in range(data_start, (ws.max_row or data_start) + 1):
            seq = ws.cell(r, c0 + 1).value  # 步骤序
            if seq is None or seq == "":
                break
            try:
                seq_i = _as_int(seq)
            except (TypeError, ValueError):
                break
            steps.append(
                流程步骤(
                    管线=name,
                    步骤序=seq_i,
                    步骤名=str(ws.cell(r, c0 + 2).value or ""),
                    判定公式=str(ws.cell(r, c0 + 3).value or ""),
                    成功跳转=_as_int(ws.cell(r, c0 + 4).value, 0),
                    失败跳转=_as_int(ws.cell(r, c0 + 5).value, 0),
                )
            )
        steps.sort(key=lambda s: s.步骤序)
        if validate_jumps and steps:
            orders = {s.步骤序 for s in steps}
            steps = [_校验跳转(s, orders) for s in steps]
        out[name] = steps
        bi += 1
    return out

def _as_bool(v):
    if v is None or v == "":
        return True
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() not in {"0", "否", "n", "no", "false", "关闭"}


def _行含(ws, row: int, title: str) -> bool:
    max_c = min(ws.max_column or 1, 80)
    for c in range(1, max_c + 1):
        if str(ws.cell(row, c).value or "").strip() == title:
            return True
    return False


def _规划面布局(ws) -> tuple[int, int, int] | None:
    """(块标题行, 表头行, 数据起始行)。正式表块标题在 R2；旧稿在 R3。"""
    for title_row in (2, 3):
        if _行含(ws, title_row, PLAN_CATALOG_TITLE) or _行含(ws, title_row, "事件目录"):
            return title_row, title_row + 1, title_row + 2
    if str(ws.cell(2, 1).value or "").strip() == PLAN_TITLE:
        return 2, 3, 4
    return None


def 是规划面(ws) -> bool:
    return _规划面布局(ws) is not None


def _横排块(ws) -> list[tuple[str, int, list[str]]]:
    """块标题、下一列表头；块之间空一列。行号跟规划面实际布局走。"""
    layout = _规划面布局(ws)
    title_row, header_row = (layout[0], layout[1]) if layout else (TITLE_ROW, HEADER_ROW)
    blocks: list[tuple[str, int, list[str]]] = []
    max_c = ws.max_column or 1
    c = 1
    while c <= max_c:
        name = ws.cell(title_row, c).value
        if name is None or name == "":
            c += 1
            continue
        name = str(name).strip()
        ncols = 0
        while c + ncols <= max_c and ws.cell(header_row, c + ncols).value not in (None, ""):
            ncols += 1
        if ncols == 0:
            c += 1
            continue
        headers = [str(ws.cell(header_row, c + i).value or "").strip() for i in range(ncols)]
        blocks.append((name, c, headers))
        c += ncols + 1
    return blocks


def _数据起始行(ws) -> int:
    layout = _规划面布局(ws)
    return layout[2] if layout else DATA_START_ROW


def _格(ws, r: int, c0: int, headers: list[str], name: str, default=""):
    try:
        i = headers.index(name)
    except ValueError:
        return default
    v = ws.cell(r, c0 + i).value
    if v is None:
        return default
    return v


def _格首(ws, r: int, c0: int, headers: list[str], names: tuple[str, ...], default=""):
    for name in names:
        if name in headers:
            return _格(ws, r, c0, headers, name, default)
    return default


def 解析管线模板(进管线, *, pvp, 规划面=False):
    raw = str(进管线 or "").strip()
    if raw in {"", "—", "-", "时间线", "日志", "再派发", "不进结算", "不进数值结算"}:
        return None
    if 规划面:
        mode = "PVP" if pvp else "PVE"
        if raw in MODE_PIPE:
            return MODE_PIPE[(raw, mode)]
        return NEW_PIPE_ALIASES.get(raw, raw)
    if raw.endswith("PVE") or raw.endswith("PVP"):
        return raw
    mapped = NEW_PIPE_ALIASES.get(raw)
    if mapped:
        suffix = "PVP" if pvp else "PVE"
        if mapped == "伤害":
            return f"伤害{suffix}"
        if mapped == "治疗":
            return f"治疗{suffix}"
        if mapped == "状态施加":
            return f"状态{suffix}"
        return mapped
    suffix = "PVP" if pvp else "PVE"
    return f"{raw}{suffix}"


def _找标题行(ws, title: str) -> int | None:
    for r in range(1, (ws.max_row or 1) + 1):
        if str(ws.cell(r, 1).value or "").strip() == title:
            return r
    return None


def _as_yes(v) -> bool:
    if v is None or v == "":
        return True
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip() not in {"0", "否", "n", "no", "false", "关闭"}


def _行转阶段(路名: str, seq, 段名, 跳过, 判定, 机制, 输出, 适用, 启用, 成功=0, 失败=0) -> 流程阶段 | None:
    if seq is None or seq == "":
        return None
    return 流程阶段(
        路名=str(路名).strip(),
        第几段=_as_int(seq),
        段名=str(段名 or "").strip(),
        跳过条件=str(跳过 or "").strip(),
        判定公式=str(判定 or "").strip(),
        调用机制=str(机制 or "").strip(),
        写出结果=str(输出 or "").strip(),
        适用=str(适用 or "共用").strip(),
        启用=_as_yes(启用),
        成功跳转=_as_int(成功, 0),
        失败跳转=_as_int(失败, 0),
    )


def _读横排阶段(ws, *, 机制块: bool) -> dict[str, list[流程阶段]]:
    out: dict[str, list[流程阶段]] = {}
    for name, c0, headers in _横排块(ws):
        has_seq = "步骤序" in headers or "阶段序" in headers
        has_pipe = "管线名" in headers
        if not has_seq:
            continue
        if 机制块 and name != PLAN_MECH_TITLE:
            continue
        if not 机制块 and (name == PLAN_MECH_TITLE or has_pipe):
            continue
        data_start = _数据起始行(ws)
        for r in range(data_start, (ws.max_row or data_start) + 1):
            seq = _格首(ws, r, c0, headers, ("步骤序", "阶段序"), None)
            if seq is None or seq == "":
                if 机制块 and _格(ws, r, c0, headers, "管线名") not in (None, "", ""):
                    continue
                if not 机制块:
                    break
                more = any(
                    _格首(ws, rr, c0, headers, ("步骤序", "阶段序"), None) not in (None, "")
                    for rr in range(r + 1, min(r + 3, (ws.max_row or r) + 1))
                )
                if not more:
                    break
                continue
            路名 = name if not 机制块 else str(_格(ws, r, c0, headers, "管线名", name) or name).strip()
            st = _行转阶段(
                路名,
                seq,
                _格首(ws, r, c0, headers, ("步骤名", "阶段名")),
                _格(ws, r, c0, headers, "跳过条件"),
                _格首(ws, r, c0, headers, ("判定公式", "判定")),
                _格(ws, r, c0, headers, "调用机制"),
                _格(ws, r, c0, headers, "输出"),
                _格(ws, r, c0, headers, "适用场景", "共用"),
                _格(ws, r, c0, headers, "启用", "是"),
                _格(ws, r, c0, headers, "成功跳转", 0),
                _格(ws, r, c0, headers, "失败跳转", 0),
            )
            if st is None:
                continue
            out.setdefault(st.路名, []).append(st)
    for name in out:
        out[name].sort(key=lambda s: s.第几段)
    return out


def _读阶段块(ws, title: str) -> dict[str, list[流程阶段]]:
    hit = _找标题行(ws, title)
    if hit is None:
        return {}
    header_row = hit + 1
    out: dict[str, list[流程阶段]] = {}
    for r in range(header_row + 1, (ws.max_row or header_row) + 1):
        name = ws.cell(r, 1).value
        if name is None or name == "":
            nxt = ws.cell(r + 1, 1).value if r < (ws.max_row or r) else None
            if nxt and str(nxt).strip() in {PLAN_EVENT_TITLE, PLAN_STAGE_TITLE, MECH_STAGE_TITLE, "机制旋钮"}:
                break
            if not any(ws.cell(r, c).value not in (None, "") for c in range(1, 10)):
                more = any(
                    ws.cell(rr, 1).value not in (None, "")
                    for rr in range(r + 1, min(r + 3, (ws.max_row or r) + 1))
                )
                if not more:
                    break
                continue
            continue
        if str(name).strip() in {PLAN_EVENT_TITLE, PLAN_STAGE_TITLE, MECH_STAGE_TITLE, "机制旋钮", "什么事件进哪条路"}:
            break
        seq = ws.cell(r, 2).value
        if seq is None or seq == "":
            continue
        st = 流程阶段(
            路名=str(name).strip(),
            第几段=_as_int(seq),
            段名=str(ws.cell(r, 3).value or "").strip(),
            跳过条件=str(ws.cell(r, 4).value or "").strip(),
            判定公式=str(ws.cell(r, 5).value or "").strip(),
            调用机制=str(ws.cell(r, 6).value or "").strip(),
            写出结果=str(ws.cell(r, 7).value or "").strip(),
            适用=str(ws.cell(r, 8).value or "共用").strip(),
            启用=_as_yes(ws.cell(r, 9).value),
        )
        out.setdefault(st.路名, []).append(st)
    for name in out:
        out[name].sort(key=lambda s: s.第几段)
    return out


def 加载阶段规划(wb) -> dict[str, list[流程阶段]]:
    out: dict[str, list[流程阶段]] = {}
    if "战斗流程" in wb.sheetnames and 是规划面(wb["战斗流程"]):
        out.update(_读横排阶段(wb["战斗流程"], 机制块=False))
        if 事件页 in wb.sheetnames:
            out.update(_读横排阶段(wb[事件页], 机制块=False))
        if out:
            return out
        return _读阶段块(wb["战斗流程"], PLAN_STAGE_TITLE)
    return {}


def 加载机制流程(wb) -> dict[str, list[流程阶段]]:
    if "战斗流程" in wb.sheetnames:
        ws = wb["战斗流程"]
        if 是规划面(ws):
            horizontal = _读横排阶段(ws, 机制块=True)
            if horizontal:
                return horizontal
    if MECH_SHEET not in wb.sheetnames:
        return {}
    return _读阶段块(wb[MECH_SHEET], MECH_STAGE_TITLE)


def 加载机制旋钮(wb) -> dict[str, float]:
    out: dict[str, float] = {}
    if "战斗流程" in wb.sheetnames:
        ws = wb["战斗流程"]
        for name, c0, headers in _横排块(ws):
            if name != PLAN_PARAM_TITLE and "参数名" not in headers:
                continue
            data_start = _数据起始行(ws)
            for r in range(data_start, (ws.max_row or data_start) + 1):
                key = _格(ws, r, c0, headers, "参数名")
                if key in (None, ""):
                    break
                try:
                    out[str(key).strip()] = float(_格(ws, r, c0, headers, "取值", 0))
                except (TypeError, ValueError):
                    continue
            if out:
                return out
    if MECH_SHEET not in wb.sheetnames:
        return out
    ws = wb[MECH_SHEET]
    hit = _找标题行(ws, "机制旋钮")
    if hit is None:
        return out
    for r in range(hit + 2, (ws.max_row or hit) + 1):
        name = ws.cell(r, 1).value
        if name is None or name == "":
            break
        if str(name).strip() == MECH_STAGE_TITLE:
            break
        try:
            out[str(name).strip()] = float(ws.cell(r, 2).value)
        except (TypeError, ValueError):
            continue
    return out


def 加载事件接入规划(wb) -> dict:
    """规划面事件：键仍是引擎种类（IMPACT…），带入口段名。"""
    from 战斗模拟.内核.事件 import 规范化事件种类

    out = {}
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        for name, c0, headers in _横排块(ws):
            if name not in EVENT_BLOCKS:
                continue
            if "事件名" not in headers and "事件" not in headers and "事件种类" not in headers:
                continue
            kind_key = "事件名" if "事件名" in headers else ("事件" if "事件" in headers else "事件种类")
            data_start = _数据起始行(ws)
            for r in range(data_start, (ws.max_row or data_start) + 1):
                raw_kind = _格(ws, r, c0, headers, kind_key, None)
                if raw_kind is None or raw_kind == "":
                    break
                mapped = 事件名到种类.get(str(raw_kind).strip(), str(raw_kind).strip())
                kind = 规范化事件种类(mapped) or mapped
                if not kind:
                    continue
                entry_raw = _格首(ws, r, c0, headers, ("入口步骤", "入口阶段"))
                entry_step = 0
                entry_name = ""
                if entry_raw not in (None, ""):
                    text = str(entry_raw).strip()
                    if text.lstrip("-").isdigit():
                        entry_step = int(float(text))
                    else:
                        entry_name = text
                out[kind] = 事件接入(
                    种类=kind,
                    进管线=str(_格(ws, r, c0, headers, "进管线") or "").strip(),
                    入口步骤=entry_step,
                    来源覆盖=str(_格(ws, r, c0, headers, "来源覆盖") or "").strip(),
                    备注=str(_格首(ws, r, c0, headers, ("说明", "处理", "备注")) or "").strip(),
                    启用=True,
                    入口段名=entry_name,
                )
    if out:
        return out
    if "战斗流程" not in wb.sheetnames:
        return {}
    ws = wb["战斗流程"]
    hit = _找标题行(ws, PLAN_EVENT_TITLE)
    if hit is None:
        return {}
    for r in range(hit + 2, (ws.max_row or hit) + 1):
        raw_kind = ws.cell(r, 1).value
        if raw_kind is None or raw_kind == "":
            break
        mapped = 事件名到种类.get(str(raw_kind).strip(), str(raw_kind).strip())
        kind = 规范化事件种类(mapped) or mapped
        if not kind:
            continue
        entry_name = str(ws.cell(r, 3).value or "").strip()
        out[kind] = 事件接入(
            种类=kind,
            进管线=str(ws.cell(r, 2).value or "").strip(),
            入口步骤=0,
            来源覆盖=str(ws.cell(r, 4).value or "").strip(),
            备注=str(ws.cell(r, 6).value or "").strip(),
            启用=_as_yes(ws.cell(r, 5).value),
            入口段名=entry_name,
        )
    return out


def 加载事件接入(wb):
    from 战斗模拟.内核.事件 import 规范化事件种类

    planned = 加载事件接入规划(wb)
    if planned:
        return planned

    ws = wb["战斗流程"]
    max_c = ws.max_column or 1
    c0 = None
    bi = 0
    while True:
        col = 1 + bi * BLOCK_STRIDE
        if col > max_c:
            break
        name = ws.cell(TITLE_ROW, col).value
        if name and str(name).strip() == EVENT_BLOCK:
            c0 = col
            break
        bi += 1
        if bi > 32:
            break
    if c0 is None:
        return {}
    out = {}
    for r in range(DATA_START_ROW, (ws.max_row or DATA_START_ROW) + 1):
        raw_kind = ws.cell(r, c0).value
        if raw_kind is None or raw_kind == "":
            break
        kind = 规范化事件种类(raw_kind)
        if not kind:
            continue
        row = 事件接入(
            种类=kind,
            进管线=str(ws.cell(r, c0 + 1).value or "").strip(),
            入口步骤=_as_int(ws.cell(r, c0 + 2).value, 0),
            来源覆盖=str(ws.cell(r, c0 + 3).value or "").strip(),
            备注=str(ws.cell(r, c0 + 4).value or "").strip(),
            启用=_as_bool(ws.cell(r, c0 + 5).value),
        )
        out[kind] = row
    return out

