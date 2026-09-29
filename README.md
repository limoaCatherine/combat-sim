# 战斗模拟

读战斗数值框架里的构筑、技能、怪物、场景和批跑任务，按行为规则打一场。仓库不包含项目框架表。

```
战斗模拟/
  pipeline.py     任务 → 编译 → 一场 → 写回
  load/           按块名和字段名读表，技能等级继承
  compile/        玩家面板、怪物属性覆盖。缺生命就停
  sim/            规则选技能，数值解析式结算
  write/          追加到对战模拟的运行结果
```

本仓库带有 `公共`（打开工作簿、定位表块、表名）。覆盖率、属性价值、多场景平衡和框架加载在另外的仓库。把这些仓库克隆到同一级目录后，启动脚本会把它们加进路径：

- scene-coverage
- attr-value
- scene-balance
- numeric-ssot

## 运行

Python 3.11+。

```bash
pip install -r requirements.txt
set BATTLE_SIM_WORKBOOK=框架表.xlsx
python 启动_战斗模拟.py
python 启动_战斗模拟.py --task 木桩场_基线 --write
```

也认 `LIMOA_FRAMEWORK`。未设置时，会在桌面和同级 `数值框架` 目录里查找 `战斗数值框架.xlsx`。批跑写出的文件在本仓库 `out/`。

旧木桩 / 首领入口已改为提示，请统一走 `启动_战斗模拟.py`。

## 许可

[MIT](LICENSE)。
