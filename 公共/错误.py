"""面向策划的可读错误。"""
from __future__ import annotations


class 数值工具错误(Exception):
    """基类。"""


class 数据缺失错误(数值工具错误):
    """工作簿缺块、缺列、缺场景等。"""


class 引用缺失错误(数值工具错误):
    """构筑/技能/效果引用不存在。"""


class 配置错误(数值工具错误):
    """路径或环境配置问题。"""


# 英文别名（代码内可选）
ShuzhiError = 数值工具错误
DataMissingError = 数据缺失错误
RefMissingError = 引用缺失错误
ConfigError = 配置错误
