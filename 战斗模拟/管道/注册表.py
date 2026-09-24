"""命名管道注册表。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

Resolver = Callable[..., dict[str, Any]]

_REGISTRY: dict[str, Resolver] = {}


def 注册(name: str, fn: Resolver) -> Resolver:
    _REGISTRY[name] = fn
    return fn


def 获取(name: str) -> Resolver:
    if name not in _REGISTRY:
        raise KeyError(f"未知管道: {name}；已注册: {list(_REGISTRY)}")
    return _REGISTRY[name]


def 列出管道() -> list[str]:
    return sorted(_REGISTRY)


def 管道注册表() -> dict[str, Resolver]:
    # 确保内置管道已加载
    from 战斗模拟.管道 import 伤害, 治疗, 仇恨, 扣血, 吸血反伤  # noqa: F401
    # 吸血反伤/仇恨 = helpers（表内已内联）；命中后/治疗后不再注册

    return dict(_REGISTRY)


list_pipelines = 列出管道
get_pipeline = 获取
pipeline_registry = 管道注册表
