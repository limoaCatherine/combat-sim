"""运行时设置：环境变量覆盖工作簿路径。"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from 公共.路径 import 发现框架路径


class 设置(BaseSettings):
    """通过环境变量覆盖默认框架工作簿路径。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    FRAMEWORK_WORKBOOK: str | None = Field(default=None)
    BATTLE_SIM_WORKBOOK: str | None = Field(default=None)

    def 工作簿路径(self) -> Path:
        for raw in (self.FRAMEWORK_WORKBOOK, self.BATTLE_SIM_WORKBOOK):
            if raw and str(raw).strip():
                return Path(str(raw).strip()).expanduser().resolve()
        found = 发现框架路径()
        if found is not None:
            return found
        return (Path.cwd() / "战斗数值框架.xlsx").resolve()


def 获取设置() -> 设置:
    return 设置()


Settings = 设置
get_settings = 获取设置
