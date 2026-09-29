"""战斗流程判定式。只执行表上写出来的函数，遇到没有实现的函数记入待对齐。"""
from __future__ import annotations

import re

_TOKEN = re.compile(
    r"\s+|&&|\|\||==|!=|<=|>=|[+\-*/()<>,]|[0-9]+(?:\.[0-9]+)?|\"[^\"]*\"|[\u4e00-\u9fffA-Za-z_][\u4e00-\u9fffA-Za-z0-9_%]*"
)


def evaluate(formula: str, host) -> object:
    text = str(formula or "").strip()
    if not text:
        return True
    tokens = [token for token in _TOKEN.findall(text) if not token.isspace()]
    if not tokens:
        return True
    parser = _Parser(tokens, host)
    value = parser._or()
    return value


class _Parser:
    def __init__(self, tokens: list[str], host):
        self.tokens = tokens
        self.host = host
        self.i = 0

    def _peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _eat(self, token: str | None = None) -> str:
        current = self._peek()
        self.i += 1
        return current if current is not None else ""

    def _or(self):
        value = self._and()
        while self._peek() == "||":
            self._eat()
            right = self._and()
            value = _truth(value) or _truth(right)
        return value

    def _and(self):
        value = self._cmp()
        while self._peek() == "&&":
            self._eat()
            right = self._cmp()
            value = _truth(value) and _truth(right)
        return value

    def _cmp(self):
        value = self._add()
        while self._peek() in ("==", "!=", "<", ">", "<=", ">="):
            op = self._eat()
            right = self._add()
            value = _compare(value, op, right)
        return value

    def _add(self):
        value = self._mul()
        while self._peek() in ("+", "-"):
            op = self._eat()
            right = self._mul()
            value = _binary(value, op, right)
        return value

    def _mul(self):
        value = self._unary()
        while self._peek() in ("*", "/"):
            op = self._eat()
            right = self._unary()
            value = _binary(value, op, right)
        return value

    def _unary(self):
        if self._peek() == "-":
            self._eat()
            value = self._unary()
            return None if value is None else -float(value)
        return self._primary()

    def _primary(self):
        token = self._peek()
        if token is None:
            return None
        if token == "(":
            self._eat()
            value = self._or()
            if self._peek() == ")":
                self._eat()
            return value
        if token.startswith('"'):
            self._eat()
            return token.strip('"')
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token):
            self._eat()
            return float(token) if "." in token else int(token)
        self._eat()
        if self._peek() == "(":
            self._eat("(")
            args = []
            if self._peek() != ")":
                args.append(self._or())
                while self._peek() == ",":
                    self._eat()
                    args.append(self._or())
            if self._peek() == ")":
                self._eat()
            return self.host.call(token, args)
        return self.host.resolve(token)


def _truth(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _binary(left, op, right):
    if left is None or right is None:
        return None
    try:
        left, right = float(left), float(right)
    except (TypeError, ValueError):
        return None
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    return left / right if right else None


def _compare(left, op, right) -> bool:
    if left is None or right is None:
        return False
    if op == "==":
        return str(left) == str(right) if isinstance(left, str) or isinstance(right, str) else float(left) == float(right)
    if op == "!=":
        return not _compare(left, "==", right)
    try:
        left, right = float(left), float(right)
    except (TypeError, ValueError):
        # 未初始化的管线变量会解析成标识符字符串，按条件不成立处理。
        return False
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    return left >= right
