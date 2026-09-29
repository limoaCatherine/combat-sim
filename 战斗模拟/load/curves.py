"""公式参数里的率值和效果式。系数、常数用工作簿里的 Xklc 定义，不另写一套减伤。"""
from __future__ import annotations

import ast
import re

from 战斗模拟.load.blocks import _blank

_QUOTE = re.compile(r'"([^"]*)"')
_RATIO = re.compile(r'"([^"/]+?)\s*/\s*\(\1\s*\+\s*"&TEXT\(D\d+')
_LEVEL = re.compile(r"(攻方等级|防方等级)")
_CALL = re.compile(r"(攻方|守方)\(([^)]+)\)")


def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in ("", "—", "-", "－"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _raw_expression(formula: str) -> str | None:
    if not formula:
        return None
    ratio = _RATIO.search(formula)
    if ratio:
        attr = ratio.group(1).strip()
        level = "防方等级" if "防方等级" in formula else "攻方等级"
        return f"{attr} / ({attr} + 系数 * {level} + 常数)"
    meaningful = [q for q in _QUOTE.findall(formula) if re.search(r"[\u4e00-\u9fff%]", q)]
    if not meaningful:
        return None
    return meaningful[-1]


def _wrap(raw: str, lo, hi) -> str:
    expr = raw
    if hi is not None:
        expr = f"最小({expr},{hi})"
    if lo is not None:
        expr = f"最大({lo},{expr})"
    return expr


def xklc(ref1: float, rate1: float, ref60: float, rate60: float) -> tuple[float, float] | None:
    """工作簿定义名 Xklc系数 / Xklc常数。毕业率必须在 (0,1)。"""
    if ref1 is None or ref60 is None or rate1 is None or rate60 is None:
        return None
    if rate1 <= 0 or rate1 >= 1 or rate60 <= 0 or rate60 >= 1:
        return None
    d1 = ref1 * (1 / rate1 - 1)
    d60 = ref60 * (1 / rate60 - 1)
    k = (d60 - d1) / 59
    c = d1 - k
    return k, c


class CurveBook:
    def __init__(self, rows: list[dict], standards: dict[str, dict], gaps: list[str]):
        self.rows = {row["参数名"]: row for row in rows}
        self.standards = standards
        self.gaps = gaps
        self._stack: list[str] = []

    def effect(self, name: str, env: dict):
        row = self.rows.get(name)
        if row is None:
            self._gap(f"战斗流程引用了效果「{name}」，公式参数里没有这一行")
            return None
        if row.get("表达式") in (None, ""):
            self._gap(f"公式参数「{name}」没有可计算的表达式")
            return None
        value = self._eval(row["表达式"], env, row)
        return value

    def _gap(self, text: str) -> None:
        if text not in self.gaps:
            self.gaps.append(text)

    def _stat(self, name: str, env: dict, row: dict | None):
        if name in ("系数", "常数", "攻方等级", "防方等级"):
            return env.get(name)
        if name in env and name not in ("攻方", "守方"):
            if name in ("对应通道增伤", "对应通道抗性", "对应动作增伤", "对应动作抗性", "对应方式增伤", "对应方式抗性", "对应武器增伤", "全武器增伤", "对应武器抗性", "全武器抗性", "元素克制矩阵倍率", "对应元素增伤", "全元素增伤", "对应元素抗性", "全元素抗性", "对应种族增伤", "全种族增伤", "对应种族抗性", "全种族抗性", "武器体型修正系数", "对应体型增伤", "全体型增伤", "对应体型抗性", "全体型抗性"):
                return env.get(name)
        owner = _owner(name, row)
        bag = env.get("守方") if owner == "守方" else env.get("攻方")
        if not isinstance(bag, dict) or name not in bag:
            return 0.0
        return bag[name]

    def _eval(self, expr: str, env: dict, row: dict | None):
        if expr in self.rows and expr not in self._stack:
            self._stack.append(expr)
            try:
                return self.effect(expr, env)
            finally:
                self._stack.pop()
        local = dict(env)
        if row and row.get("系数") is not None:
            local["系数"] = row["系数"]
            local["常数"] = row["常数"]
        text = expr.replace("MAX", "最大").replace("MIN", "最小")

        def repl(match: re.Match) -> str:
            side = match.group(1)
            stat = match.group(2).strip()
            bag = local.get(side)
            if not isinstance(bag, dict) or stat not in bag:
                return "0"
            return str(float(bag[stat]))

        text = _CALL.sub(repl, text)
        return _arith(text, lambda name: self._value_of(name, local, row))

    def _value_of(self, name: str, env: dict, row: dict | None):
        if name in self.rows and name not in self._stack:
            self._stack.append(name)
            try:
                return self.effect(name, env)
            finally:
                self._stack.pop()
        return self._stat(name, env, row)


def _side_of(name: str, expr: str | None) -> str:
    """取值方写在公式里：出现防方等级，或属性名本身是守方的防御、格挡、抗性、免伤。"""
    text = str(expr or "")
    if "防方等级" in text:
        return "守方"
    if any(token in name for token in ("防御", "抗暴", "格挡", "闪避", "抗性", "免伤")) and "穿透" not in name and "增伤" not in name:
        return "守方"
    return "攻方"


def _owner(name: str, row: dict | None) -> str:
    if row and row.get("参数名") == name and row.get("取值方") in ("攻方", "守方"):
        return row["取值方"]
    if row and row.get("参数名") == name and "防方等级" in str(row.get("表达式") or ""):
        return "守方"
    if any(token in name for token in ("防御", "抗暴", "格挡", "闪避", "抗性", "免伤")) and "穿透" not in name and "增伤" not in name:
        return "守方"
    return "攻方"


def _arith(expr: str, resolve):
    """四则、最大、最小。名字交给 resolve，缺数则整式无结果。"""
    replaced = expr
    names = sorted(set(re.findall(r"[\u4e00-\u9fffA-Za-z%][\u4e00-\u9fffA-Za-z0-9_%]*", expr)), key=len, reverse=True)
    local = {}
    for index, name in enumerate(names):
        if name in ("最大", "最小"):
            continue
        value = resolve(name)
        if value is None:
            return None
        token = f"v{index}"
        local[token] = float(value)
        replaced = replaced.replace(name, token)
    replaced = replaced.replace("最大", "max").replace("最小", "min")
    if not re.fullmatch(r"(?:max|min|v\d+|\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?|[+\-*/(),\s])+", replaced):
        return None
    try:
        tree = ast.parse(replaced, mode="eval")
    except SyntaxError:
        return None
    return _eval_node(tree.body, local)


def _eval_node(node, local):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        return local[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_node(node.operand, local)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _eval_node(node.left, local), _eval_node(node.right, local)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right if right else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("max", "min"):
        args = [_eval_node(arg, local) for arg in node.args]
        if any(item is None for item in args):
            return None
        return max(args) if node.func.id == "max" else min(args)
    return None


def _standards(ws) -> dict[str, dict]:
    """最终值 定义名用的列：K 属性名，M 开放等级，O 起始值，P 毕业值，Q 曲线指数。"""
    out = {}
    for row in range(4, 420):
        name = ws.cell(row, 11).value
        if _blank(name):
            continue
        out[str(name).strip()] = {
            "开放等级": _num(ws.cell(row, 13).value),
            "起始值": _num(ws.cell(row, 15).value),
            "毕业值": _num(ws.cell(row, 16).value),
            "曲线指数": _num(ws.cell(row, 17).value),
        }
    return out


def _final_value(standards: dict, name: str, level: float) -> float | None:
    """定义名 最终值。开放等级之前为 0。"""
    row = standards.get(name)
    if not row:
        return None
    start = row.get("起始值")
    end = row.get("毕业值")
    power = row.get("曲线指数")
    opened = row.get("开放等级")
    if start is None or end is None:
        return None
    if power is None:
        power = 1.0
    if opened is None:
        opened = 1.0
    level = max(1.0, min(60.0, level))
    if level < opened:
        return 0.0
    if opened >= 60:
        return end
    if start == 0:
        span = (level - opened + 1) / (61 - opened)
    else:
        span = (level - opened) / (60 - opened)
    return start + (end - start) * (span ** power)


def load_curves(ws_formula, ws_standard, gaps: list[str]) -> CurveBook:
    standards = _standards(ws_standard)
    rows = []
    for row in range(30, 80):
        name = ws_formula.cell(row, 1).value
        if _blank(name) or str(name).strip() == "参数名":
            continue
        formula = ws_formula.cell(row, 3).value
        raw = _raw_expression(str(formula or ""))
        lo = _num(ws_formula.cell(row, 6).value)
        hi = _num(ws_formula.cell(row, 7).value)
        attr = ws_formula.cell(row, 8).value
        rate1 = _num(ws_formula.cell(row, 10).value)
        rate60 = _num(ws_formula.cell(row, 12).value)
        ref_name = str(attr).strip() if not _blank(attr) else None
        ref1 = _final_value(standards, ref_name, 1) if ref_name and rate1 is not None else None
        ref60 = _final_value(standards, ref_name, 60) if ref_name and rate60 is not None else None
        coeff = xklc(ref1, rate1, ref60, rate60) if rate1 is not None else None
        if rate1 is not None and coeff is None:
            gaps.append(f"公式参数「{name}」的一级或六十级参考量无法从标准属性算出，Xklc 系数空着")
        record = {
            "参数名": str(name).strip(),
            "对应属性": ref_name,
            "表达式": _wrap(raw, lo, hi) if raw else None,
            "取值方": _side_of(str(name), raw),
            "系数": None if coeff is None else coeff[0],
            "常数": None if coeff is None else coeff[1],
            "下限": lo,
            "上限": hi,
        }
        if raw is None:
            gaps.append(f"公式参数「{name}」的计算公式单元格无法抽出表达式")
        rows.append(record)
    if not any(item["参数名"] == "物理免伤效果" for item in rows):
        gaps.append("公式参数没有「物理免伤效果」行")
    return CurveBook(rows, standards, gaps)


def load_transfers(ws_attr) -> dict[str, str]:
    """转入公式。实体契约、以及标成「输入」或常数、四则式的属性都会收下。

    Excel 的 LET/INDEX 公式留给公式参数去算，不在这里当转入式。
    """
    out = {}
    for row in range(8, 420):
        name = ws_attr.cell(row, 2).value
        if _blank(name):
            continue
        formula = ws_attr.cell(row, 16).value
        if _blank(formula):
            continue
        text = str(formula).strip()
        if text.startswith("_xlfn") or "INDEX(" in text or text.startswith("="):
            continue
        contract = str(ws_attr.cell(row, 17).value or "").strip()
        simple = text == "输入" or _num(text) is not None or re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9_%+\-*/().\s]+", text)
        if contract == "是" or simple:
            out[str(name).strip()] = text
    return out
