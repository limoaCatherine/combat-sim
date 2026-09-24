# 战斗模拟

表驱动的离散事件战斗仿真，迭代中。面板、技能、效果、场景和公式参数都从框架工作簿读取。仓库不包含项目框架表。

伤害管线依次为：无敌、必中或必闪、属性闪避、免伤、克制、格挡、暴击、乘区、爆伤、受伤修正、吸血反伤。另有治疗、护盾先进先出、仇恨、光环和技能路由。蒙特卡洛和解析期望对照。平衡调整以提案输出，不写回正式配置。

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
python 启动_战斗模拟.py --scene _smoke_ -n 1
pytest -q
```

也认 `LIMOA_FRAMEWORK`。未设置时，会在桌面和同级 `数值框架` 目录里查找 `战斗数值框架.xlsx`。批跑写出的文件在本仓库 `out/`。

## 许可

[MIT](LICENSE)。
