"""技能段表达式：把表内中文属性名换成面板数字后求值。不发明系数。"""
from __future__ import annotations

import ast
import operator
import re
from typing import Any, Mapping

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def 切段(text: str | None) -> list[str]:
    if not text or not str(text).strip():
        return []
    parts = re.split(r"[;；|\n]+", str(text))
    return [p.strip() for p in parts if p.strip()]


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return float(_OPS[type(node.op)](_eval_ast(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return float(_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right)))
    raise ValueError(f"不支持的表达式节点: {type(node).__name__}")


def 求值(expr: str, panel: Mapping[str, Any] | None = None) -> float:
    pan = dict(panel or {})
    s = str(expr).strip()
    if not s:
        return 0.0
    keys = sorted((k for k in pan if k), key=len, reverse=True)
    for k in keys:
        if k in s:
            v = pan[k]
            if v is None:
                continue
            s = s.replace(str(k), str(float(v)))
    if re.search(r"[\u4e00-\u9fff]", s):
        raise ValueError(f"表达式含未绑定属性: {expr}")
    tree = ast.parse(s, mode="eval")
    return _eval_ast(tree)
