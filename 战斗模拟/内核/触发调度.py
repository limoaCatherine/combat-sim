"""效果触发（Proc）调度：读表 → 钩子 → 概率×ICD×条件 → PROC 事件 / 管线请求。

不新增战斗流程 sheet 管线；成功后走既有 伤害/治疗/效果事件/驱散 请求或 DES 事件。
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from 战斗模拟.内核.事件 import 事件调度器, 事件种类

# 结算时机 → 引擎钩子名（同源；表值与钩子对齐）
钩子_命中时 = "命中时"
钩子_暴击时 = "暴击时"
钩子_攻击时 = "攻击时"
钩子_受击时 = "受击时"
钩子_光环施加 = "光环施加"
钩子_光环到期 = "光环到期"
钩子_每跳动 = "每跳动"
钩子_敌人进入 = "敌人进入"

# 常驻不订阅事件族（面板修正由异常挂载负责）
_非事件时机 = frozenset({"常驻", "永久", ""})

_事件钩子 = frozenset(
    {
        钩子_命中时,
        钩子_暴击时,
        钩子_攻击时,
        钩子_受击时,
        钩子_光环施加,
        钩子_光环到期,
        钩子_每跳动,
        钩子_敌人进入,
    }
)

# 表值别名归一
_时机别名: dict[str, str] = {
    "命中": 钩子_命中时,
    "暴击": 钩子_暴击时,
    "攻击": 钩子_攻击时,
    "受击": 钩子_受击时,
    "施加时": 钩子_光环施加,
    "光环施加时": 钩子_光环施加,
    "aura_apply": 钩子_光环施加,
    "到期": 钩子_光环到期,
    "光环到期时": 钩子_光环到期,
    "aura_expire": 钩子_光环到期,
    "跳动": 钩子_每跳动,
    "dot": 钩子_每跳动,
    "hot": 钩子_每跳动,
    "on_hit": 钩子_命中时,
    "on_crit": 钩子_暴击时,
    "on_attack": 钩子_攻击时,
    "on_struck": 钩子_受击时,
}

_额外动作动词 = re.compile(
    r"^\s*(伤害|治疗|施加|挂载|驱散|偷取增益|清减益)"
    r"\s*(?:\((.*)\))?\s*$"
)

_条件已提示: set[str] = set()


def 归一结算时机(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if s in _非事件时机 or s in _事件钩子:
        return s
    low = s.lower()
    if low in _时机别名:
        return _时机别名[low]
    if s in _时机别名:
        return _时机别名[s]
    return s


@dataclass
class 触发定义:
    """单条效果触发契约（效果总表 ⑥触发结算 + ⑪额外动作）。"""

    效果代号: str
    结算时机: str = ""
    触发概率百分: float = 100.0
    结算内置冷却: float = 0.0
    结算条件: str = ""
    生效时机: str = ""
    额外动作: list[str] = field(default_factory=list)
    原始行: dict[str, Any] = field(default_factory=dict)

    @property
    def 钩子(self) -> str:
        return 归一结算时机(self.结算时机)

    @property
    def 是事件族(self) -> bool:
        return self.钩子 in _事件钩子


def _fnum(v: Any, default: float | None = 0.0) -> float | None:
    if v is None or str(v).strip() in ("", "—", "-", "无"):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _解析额外动作列表(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("额外动作1", "额外动作2", "额外动作3"):
        v = row.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s and s not in ("—", "-", "无"):
            out.append(s)
    # 兼容合并列
    merged = row.get("额外动作")
    if merged and not out:
        for part in re.split(r"[;；\n]+", str(merged)):
            p = part.strip()
            if p:
                out.append(p)
    return out


def 解析额外动作(原文: str) -> dict[str, Any] | None:
    """解析 `伤害(...)` / `治疗(...)` / `施加(...)` / `驱散(...)` 等。

    返回管线请求描述；无法识别则保留原文供上层记日志。
    """
    s = str(原文 or "").strip()
    if not s:
        return None
    m = _额外动作动词.match(s)
    if not m:
        return {"动词": "未知", "参数": "", "管线族": None, "原文": s}
    verb = m.group(1)
    args = (m.group(2) or "").strip()
    管线族 = {
        "伤害": "伤害",
        "治疗": "治疗",
        "施加": "效果事件",
        "挂载": "效果事件",
        "驱散": "驱散",
        "偷取增益": "驱散",
        "清减益": "驱散",
    }.get(verb)
    return {"动词": verb, "参数": args, "管线族": 管线族, "原文": s}


def 行转触发定义(row: dict[str, Any]) -> 触发定义 | None:
    code = row.get("状态代号") or row.get("效果代号") or row.get("代号")
    if code is None or str(code).strip() == "":
        return None
    timing = 归一结算时机(row.get("结算时机"))
    # 无结算时机且无额外动作 → 非触发行，跳过
    extras = _解析额外动作列表(row)
    if not timing and not extras:
        return None
    # 事件钩子缺触发概率%则跳过，禁止发明 100%；常驻不掷骰
    raw_p = row.get("触发概率%")
    if timing in _非事件时机:
        p = 100.0
    elif raw_p is None or str(raw_p).strip() in ("", "—", "-"):
        return None
    else:
        p = _fnum(raw_p, None)
        if p is None:
            return None
    return 触发定义(
        效果代号=str(code).strip(),
        结算时机=timing or str(row.get("结算时机") or "").strip(),
        触发概率百分=p,
        结算内置冷却=_fnum(row.get("结算内置冷却"), 0.0),
        结算条件=str(row.get("结算条件") or "").strip(),
        生效时机=str(row.get("生效时机") or "").strip(),
        额外动作=extras,
        原始行={k: v for k, v in row.items() if v is not None},
    )


def 加载触发定义(wb_or_path: Any) -> list[触发定义]:
    """从效果总表加载触发定义（仅保留有结算时机或额外动作的行）。"""
    from 公共.常量.工作表 import SHEET_效果总表, 表头行_目录, 数据起始行_目录
    from 公共.工作簿.打开 import 打开工作簿
    from 公共.工作簿.目录页 import 读表头映射, 迭代数据行

    own = False
    if isinstance(wb_or_path, (str, Path)):
        wb = 打开工作簿(wb_or_path, data_only=True)
        own = True
    else:
        wb = wb_or_path
    try:
        if SHEET_效果总表 not in wb.sheetnames:
            return []
        ws = wb[SHEET_效果总表]
        headers = 读表头映射(ws, header_row=表头行_目录)
        out: list[触发定义] = []
        for _r, row in 迭代数据行(ws, headers, data_start=数据起始行_目录):
            d = 行转触发定义(row)
            if d is not None:
                out.append(d)
        return out
    finally:
        if own:
            wb.close()


def 评价结算条件(条件: str, 上下文: dict[str, Any] | None) -> bool:
    """最小条件求值；复杂式暂时 True + TODO 警告（只告警一次）。"""
    expr = str(条件 or "").strip()
    if not expr or expr in ("—", "-", "无", "true", "True"):
        return True
    ctx = 上下文 or {}
    marks = set(ctx.get("标记") or [])
    # 简单标记名 / 已暴击 / 已闪避
    if expr in ("已暴击", "暴击"):
        return bool(ctx.get("暴击") or "已暴击" in marks)
    if expr in ("已闪避", "闪避"):
        return bool(ctx.get("闪避") or "已闪避" in marks)
    if expr in ("命中", "已命中"):
        return bool(ctx.get("命中", True)) and "已闪避" not in marks
    if expr.startswith("!") or expr.startswith("不"):
        # 极简否定：!已暴击
        inner = expr.lstrip("!！不").strip()
        return not 评价结算条件(inner, ctx)
    # 标记集合成员
    if expr in marks or expr in set(ctx.get("状态") or []):
        return True
    # 上下文真值键
    if expr in ctx:
        return bool(ctx[expr])
    key = f"cond:{expr}"
    if key not in _条件已提示:
        _条件已提示.add(key)
        warnings.warn(
            f"结算条件暂未求值，按 True 放行（TODO）: {expr!r}",
            stacklevel=2,
        )
    return True


@dataclass
class 触发尝试结果:
    效果代号: str
    钩子: str
    成功: bool
    原因: str = ""
    来源: str = ""
    目标: str = ""
    动作: list[str] = field(default_factory=list)
    管线请求: list[dict[str, Any]] = field(default_factory=list)
    事件号: int | None = None


class 触发调度器:
    """按钩子过滤效果 → 条件 → ICD → 概率 → 入队 PROC / 回调。"""

    def __init__(
        self,
        定义列表: Iterable[触发定义] | None = None,
        *,
        工作簿路径: str | Path | None = None,
        rng: Any = None,
        调度器: 事件调度器 | None = None,
        日志: Any = None,
        成功回调: Callable[[触发尝试结果], None] | None = None,
    ) -> None:
        self.定义: list[触发定义] = []
        self._按钩子: dict[str, list[触发定义]] = {}
        self._按代号: dict[str, 触发定义] = {}
        # ICD：上次成功触发时刻 (entity_id, effect_code) → t_ms
        self._icd_到期: dict[tuple[str, str], float] = {}
        self.rng = rng
        self.调度器 = 调度器
        self.日志 = 日志
        self.成功回调 = 成功回调
        self.尝试次数 = 0
        self.成功次数 = 0
        self.冷却拦截次数 = 0
        self.概率失败次数 = 0
        self.条件失败次数 = 0

        if 定义列表 is not None:
            self.注入定义(定义列表)
        elif 工作簿路径 is not None:
            self.加载自工作簿(工作簿路径)

    def 注入定义(self, 定义列表: Iterable[触发定义]) -> None:
        self.定义 = list(定义列表)
        self._重建索引()

    def 加载自工作簿(self, path: str | Path) -> int:
        defs = 加载触发定义(path)
        self.注入定义(defs)
        return len(defs)

    def _重建索引(self) -> None:
        self._按钩子 = {}
        self._按代号 = {}
        for d in self.定义:
            self._按代号[d.效果代号] = d
            h = d.钩子
            if h in _事件钩子:
                self._按钩子.setdefault(h, []).append(d)

    def 重置运行时(self) -> None:
        self._icd_到期.clear()
        self.尝试次数 = 0
        self.成功次数 = 0
        self.冷却拦截次数 = 0
        self.概率失败次数 = 0
        self.条件失败次数 = 0

    def 取定义(self, 效果代号: str) -> 触发定义 | None:
        return self._按代号.get(效果代号)

    def 订阅列表(self, 钩子: str) -> list[触发定义]:
        return list(self._按钩子.get(归一结算时机(钩子), []))

    def _icd_键(self, 实体id: str, 效果代号: str) -> tuple[str, str]:
        return (str(实体id), str(效果代号))

    def _icd_可用(self, 实体id: str, 定义: 触发定义, 现在毫秒: float) -> bool:
        if float(定义.结算内置冷却 or 0) <= 0:
            return True
        key = self._icd_键(实体id, 定义.效果代号)
        until = self._icd_到期.get(key)
        if until is None:
            return True
        return float(现在毫秒) >= float(until)

    def _记下_icd(self, 实体id: str, 定义: 触发定义, 现在毫秒: float) -> None:
        icd = float(定义.结算内置冷却 or 0)
        if icd <= 0:
            return
        self._icd_到期[self._icd_键(实体id, 定义.效果代号)] = float(现在毫秒) + icd

    def _掷概率(self, 百分: float) -> bool:
        p = float(百分)
        if p >= 100.0:
            return True
        if p <= 0.0:
            return False
        rng = self.rng
        if rng is None:
            # 无 RNG：仅 100% 视为成功（与伤害管线「无 RNG 不触发概率」一致）
            return False
        roll = float(rng.random())
        return roll < (p / 100.0)

    def 尝试触发(
        self,
        定义: 触发定义,
        *,
        现在毫秒: float,
        来源id: str,
        目标id: str,
        上下文: dict[str, Any] | None = None,
        钩子: str | None = None,
        入队: bool = True,
    ) -> 触发尝试结果:
        """单条定义尝试；供测试与内部钩子复用。"""
        hook = 钩子 or 定义.钩子
        self.尝试次数 += 1
        owner = 来源id or ""

        if not 评价结算条件(定义.结算条件, 上下文):
            self.条件失败次数 += 1
            res = 触发尝试结果(
                效果代号=定义.效果代号,
                钩子=hook,
                成功=False,
                原因="条件未满足",
                来源=来源id,
                目标=目标id,
            )
            self._记日志(现在毫秒, res)
            return res

        if not self._icd_可用(owner, 定义, 现在毫秒):
            self.冷却拦截次数 += 1
            res = 触发尝试结果(
                效果代号=定义.效果代号,
                钩子=hook,
                成功=False,
                原因="ICD",
                来源=来源id,
                目标=目标id,
            )
            self._记日志(现在毫秒, res)
            return res

        if not self._掷概率(定义.触发概率百分):
            self.概率失败次数 += 1
            res = 触发尝试结果(
                效果代号=定义.效果代号,
                钩子=hook,
                成功=False,
                原因="概率未中",
                来源=来源id,
                目标=目标id,
            )
            self._记日志(现在毫秒, res)
            return res

        # 成功
        self._记下_icd(owner, 定义, 现在毫秒)
        self.成功次数 += 1
        请求 = []
        for act in 定义.额外动作:
            parsed = 解析额外动作(act)
            if parsed:
                请求.append(parsed)
        res = 触发尝试结果(
            效果代号=定义.效果代号,
            钩子=hook,
            成功=True,
            原因="ok",
            来源=来源id,
            目标=目标id,
            动作=list(定义.额外动作),
            管线请求=请求,
        )
        if 入队 and self.调度器 is not None:
            payload = {
                "效果代号": 定义.效果代号,
                "来源": 来源id,
                "目标": 目标id,
                "动作": list(定义.额外动作),
                "管线请求": 请求,
                "钩子": hook,
                "生效时机": 定义.生效时机,
            }
            # 依生效时机 / 额外动作发衍生事件请求（仍不跑新管线块）
            衍生 = self._衍生事件请求(
                定义, 来源id, 目标id, 请求, 现在毫秒=float(现在毫秒)
            )
            if 衍生:
                payload["衍生事件"] = 衍生
            res.事件号 = self.调度器.调度(
                float(现在毫秒),
                事件种类.触发.value,
                payload,
            )
            # 立即调度衍生 DES 事件（DOT/HOT/AURA / 管线手递）
            for de in 衍生:
                self.调度器.调度(
                    float(de.get("时间毫秒", 现在毫秒)),
                    str(de["种类"]),
                    dict(de.get("载荷") or {}),
                )
        if self.成功回调 is not None:
            try:
                self.成功回调(res)
            except Exception:
                pass
        self._记日志(现在毫秒, res)
        return res

    def _衍生事件请求(
        self,
        定义: 触发定义,
        来源id: str,
        目标id: str,
        请求: list[dict[str, Any]],
        *,
        现在毫秒: float = 0.0,
    ) -> list[dict[str, Any]]:
        """额外动作指向伤害/治疗/施加/驱散时，生成事件或管线手递描述。"""
        out: list[dict[str, Any]] = []
        for req in 请求:
            fam = req.get("管线族")
            verb = req.get("动词")
            if fam == "伤害":
                out.append(
                    {
                        "种类": 事件种类.命中.value,
                        "时间毫秒": None,  # 由调用方填
                        "载荷": {
                            "攻方id": 来源id,
                            "守方id": 目标id,
                            "效果代号": 定义.效果代号,
                            "管线请求": "伤害",
                            "来源触发": True,
                            "参数": req.get("参数"),
                        },
                    }
                )
            elif fam == "治疗":
                out.append(
                    {
                        "种类": 事件种类.命中.value,
                        "时间毫秒": None,
                        "载荷": {
                            "攻方id": 来源id,
                            "守方id": 目标id,
                            "效果代号": 定义.效果代号,
                            "管线请求": "治疗",
                            "来源触发": True,
                            "参数": req.get("参数"),
                        },
                    }
                )
            elif fam in ("效果事件", "异常") or verb in ("施加", "挂载"):
                kind = 事件种类.光环施加.value
                # 生效时机暗示跳转
                eff = (定义.生效时机 or "").strip()
                if "跳" in eff and "立即" not in eff:
                    # 由效果事件管线决定 DOT/HOT；此处先挂光环
                    pass
                out.append(
                    {
                        "种类": kind,
                        "时间毫秒": None,
                        "载荷": {
                            "来源id": 来源id,
                            "目标id": 目标id,
                            "效果代号": 定义.效果代号,
                            "参数": req.get("参数"),
                            "来源触发": True,
                            "管线请求": "效果事件",
                        },
                    }
                )
            elif fam == "驱散":
                out.append(
                    {
                        "种类": 事件种类.驱散.value,
                        "时间毫秒": None,
                        "载荷": {
                            "来源id": 来源id,
                            "目标id": 目标id,
                            "效果代号": 定义.效果代号,
                            "参数": req.get("参数"),
                            "来源触发": True,
                            "管线请求": "驱散",
                        },
                    }
                )
        for de in out:
            de["时间毫秒"] = float(现在毫秒)
        return out

    def 处理钩子(
        self,
        钩子: str,
        *,
        现在毫秒: float,
        来源id: str,
        目标id: str,
        上下文: dict[str, Any] | None = None,
        额外效果代号: str | Iterable[str] | None = None,
        入队: bool = True,
    ) -> list[触发尝试结果]:
        """对订阅该钩子的全部效果尝试触发；可附加「刚挂上的光环自身」。"""
        hook = 归一结算时机(钩子)
        seen: set[str] = set()
        results: list[触发尝试结果] = []
        for d in self._按钩子.get(hook, []):
            if d.效果代号 in seen:
                continue
            seen.add(d.效果代号)
            results.append(
                self.尝试触发(
                    d,
                    现在毫秒=现在毫秒,
                    来源id=来源id,
                    目标id=目标id,
                    上下文=上下文,
                    钩子=hook,
                    入队=入队,
                )
            )
        # 光环自身：若结算时机匹配当前钩子
        extras: list[str] = []
        if 额外效果代号:
            if isinstance(额外效果代号, str):
                extras = [额外效果代号]
            else:
                extras = [str(x) for x in 额外效果代号]
        for code in extras:
            if code in seen:
                continue
            d = self._按代号.get(code)
            if d is None:
                continue
            if d.钩子 != hook:
                continue
            seen.add(code)
            results.append(
                self.尝试触发(
                    d,
                    现在毫秒=现在毫秒,
                    来源id=来源id,
                    目标id=目标id,
                    上下文=上下文,
                    钩子=hook,
                    入队=入队,
                )
            )
        return results

    def _记日志(self, 现在毫秒: float, res: 触发尝试结果) -> None:
        if self.日志 is None:
            return
        try:
            self.日志.append(
                时间毫秒=float(现在毫秒),
                事件种类=事件种类.触发.value if res.成功 else "PROC_ATTEMPT",
                攻方id=res.来源,
                守方id=res.目标,
                技能或效果=res.效果代号,
                结果={
                    "成功": res.成功,
                    "原因": res.原因,
                    "钩子": res.钩子,
                    "动作": list(res.动作),
                    "管线请求": list(res.管线请求),
                    "事件号": res.事件号,
                },
            )
        except Exception:
            pass

    def 指标快照(self) -> dict[str, int]:
        return {
            "Proc尝试次数": int(self.尝试次数),
            "Proc触发次数": int(self.成功次数),
            "Proc冷却拦截": int(self.冷却拦截次数),
            "Proc概率失败": int(self.概率失败次数),
            "Proc条件失败": int(self.条件失败次数),
        }


# 英文别名
TriggerDef = 触发定义
TriggerDispatcher = 触发调度器
TriggerAttempt = 触发尝试结果
load_trigger_defs = 加载触发定义
normalize_trigger_timing = 归一结算时机
