"""数值解析式。只接受攻方/守方属性和四则运算。"""
from __future__ import annotations

import ast
import re

_CALL = re.compile(r"(攻方|守方)\(([^)]+)\)")


def 改系数(expr: str, op: str, amount: float) -> str:
    """把精通的加、乘、设落到解析式最后一个系数上。没有系数时，加成按整段倍率。"""
    text = str(expr)
    match = None
    for match in re.finditer(r"\d+(?:\.\d+)?", text):
        pass
    if match is None:
        if op == "加":
            return f"({text})*(1+{amount:g})"
        if op == "乘":
            return f"({text})*({amount:g})"
        return text
    value = float(match.group())
    if op == "加":
        value += amount
    elif op == "乘":
        value *= amount
    elif op in ("设", "覆盖"):
        value = amount
    else:
        return text
    return text[: match.start()] + f"{value:g}" + text[match.end() :]


def 求值(expr, attacker: dict, defender: dict) -> float:
    if expr in (None, ""):
        return 0.0
    if isinstance(expr, (int, float)) and not isinstance(expr, bool):
        return float(expr)

    def repl(match: re.Match) -> str:
        source = attacker if match.group(1) == "攻方" else defender
        stat = match.group(2).strip()
        value = source.get(stat, 0) or 0
        return str(float(value))

    text = _CALL.sub(repl, str(expr).replace("×", "*"))
    if not re.fullmatch(r"[0-9eE.+\-*/() ]+", text):
        return 0.0
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return 0.0
    return float(_eval(tree.body))


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right if right else 0.0
    raise ValueError("不支持的数值解析式")
