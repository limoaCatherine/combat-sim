"""运行时设置：环境变量覆盖工作簿路径。"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from 公共.路径 import 发现框架路径


class 设置(BaseSettings):
    """LIMOA_FRAMEWORK / BATTLE_SIM_WORKBOOK 均可覆盖默认框架表。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LIMOA_FRAMEWORK: str | None = Field(default=None)
    BATTLE_SIM_WORKBOOK: str | None = Field(default=None)

    def 工作簿路径(self) -> Path:
        for raw in (self.LIMOA_FRAMEWORK, self.BATTLE_SIM_WORKBOOK):
            if raw and str(raw).strip():
                return Path(str(raw).strip()).expanduser().resolve()
        found = 发现框架路径()
        if found is not None:
            return found
        # 默认 Desktop 相对布局占位（即使文件尚不存在也给出期望路径）
        return Path("../数值框架/战斗数值框架.xlsx").resolve()


def 获取设置() -> 设置:
    return 设置()


# 英文别名
Settings = 设置
get_settings = 获取设置
