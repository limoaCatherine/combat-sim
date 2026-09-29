"""按战斗流程的步骤序执行。跳转 0 表示顺序下一步，-1 表示结束。"""
from __future__ import annotations

import random

from 战斗模拟.load.xlsx_xml import read_sheet
from 战斗模拟.sim.dsl import evaluate

_DEFENDER_WORDS = ("防御", "抗暴")


class FlowHost:
    def __init__(self, curves, pipes: dict, gaps: list[str], rng: random.Random):
        self.curves = curves
        self.pipes = pipes
        self.gaps = gaps
        self.rng = rng
        self.var: dict[str, object] = {}
        self.marks: set[str] = set()
        self.atk = None
        self.dfd = None
        self.target = None
        self.env: dict = {}
        self.skill: dict = {}
        self._seen_calls: set[str] = set()

    def bind(self, attacker, defender, skill: dict, env: dict) -> None:
        self.atk = attacker
        self.dfd = defender
        self.target = defender
        self.skill = skill
        self.env = env
        self.var = {}
        self.marks = set()
        self.var["当前生命"] = defender["生命值"]
        self.var["护盾层数"] = len(defender.get("护盾层") or [])
        self.var["治疗吸收层数"] = len(defender.get("治疗吸收层") or [])
        self.var["仇恨系数"] = env.get("仇恨系数")
        self.var["伤害类型"] = env.get("伤害类型")
        self.var["伤害来源"] = env.get("伤害来源")
        self.var["命中位"] = env.get("命中位")
        self.var["暴击位"] = env.get("暴击位")
        self.var["管线伤害"] = env.get("管线伤害", 0)
        self.var["治疗值"] = env.get("治疗值", 0)
        self.var["护盾值"] = env.get("护盾值", 0)
        # 零伤短路会跳过「初始化护盾吸收量」，后续判定仍会读这些量。
        self.var.setdefault("护盾吸收量", 0)
        self.var.setdefault("护盾游标", 0)
        self.var.setdefault("本层吸收", 0)
        self.var.setdefault("结算伤害", 0)
        self.var.setdefault("实际扣血", 0)
        self.var.setdefault("最终伤害", 0)
        self.var.setdefault("吸血量", 0)
        self.var.setdefault("反伤量", 0)
        self.var.setdefault("实际反伤扣血", 0)
        self.var.setdefault("伤害仇恨", 0)
        self.var.setdefault("过量伤害", 0)
        self.var.setdefault("实际护盾", 0)
        for key, value in env.items():
            if key not in self.var and isinstance(value, (int, float, str)):
                self.var[key] = value

    def resolve(self, name: str):
        if name in self.var:
            return self.var[name]
        if name == "生命空档" and self.target is not None:
            return max(0.0, self.target["生命上限"] - self.target["生命值"])
        if name == "护盾层数" and self.target is not None:
            return len(self.target.get("护盾层") or [])
        if name == "治疗吸收层数" and self.target is not None:
            return len(self.target.get("治疗吸收层") or [])
        if name == "空":
            return ""
        return name

    def call(self, name: str, args: list):
        if name in ("攻方", "守方"):
            bag = _stats(self.atk if name == "攻方" else self.dfd)
            stat = str(args[0]) if args else ""
            if stat not in bag:
                return 0
            return bag[stat]
        if name == "随机":
            return self.rng.random()
        if name == "效果":
            return self._effect(args)
        if name == "最大":
            nums = [item for item in args if isinstance(item, (int, float))]
            return max(nums) if nums else None
        if name == "最小":
            nums = [item for item in args if isinstance(item, (int, float))]
            return min(nums) if nums else None
        if name == "有标记":
            return str(args[0]) in self.marks or str(args[0]) in (self.target or {}).get("标记", ())
        if name == "有状态":
            return str(args[0]) in (self.target or {}).get("状态", ())
        if name == "标记":
            self.marks.add(str(args[0]))
            return True
        if name == "取消标记":
            self.marks.discard(str(args[0]))
            return True
        if name == "设结算目标":
            self.target = self.dfd if str(args[0]) == "守方" else self.atk
            self.var["当前生命"] = self.target["生命值"]
            self.var["护盾层数"] = len(self.target.get("护盾层") or [])
            return True
        if name == "进入管线":
            self.run(str(args[0]))
            return True
        if name == "取护盾层":
            layers = (self.target or {}).get("护盾层") or []
            index = int(args[0])
            return layers[index] if 0 <= index < len(layers) else None
        if name == "护盾剩余容量":
            layer = args[0]
            return 0 if not isinstance(layer, dict) else layer.get("剩余", 0)
        if name == "护盾类型可吸收":
            layer, kind = args[0], str(args[1])
            if not isinstance(layer, dict):
                return False
            absorb = str(layer.get("类型") or "")
            return absorb in ("", "全部") or kind in absorb
        if name == "扣减护盾层":
            layer, amount = args
            if isinstance(layer, dict) and isinstance(amount, (int, float)):
                layer["剩余"] = max(0.0, layer.get("剩余", 0) - float(amount))
            return True
        if name == "取治疗吸收层":
            layers = (self.target or {}).get("治疗吸收层") or []
            index = int(args[0])
            return layers[index] if 0 <= index < len(layers) else None
        if name == "治疗吸收剩余容量":
            layer = args[0]
            return 0 if not isinstance(layer, dict) else layer.get("剩余", 0)
        if name == "扣减治疗吸收层":
            layer, amount = args
            if isinstance(layer, dict) and isinstance(amount, (int, float)):
                layer["剩余"] = max(0.0, layer.get("剩余", 0) - float(amount))
            return True
        if name == "设当前生命":
            if isinstance(args[0], (int, float)) and self.target is not None:
                self.target["生命值"] = float(args[0])
                self.var["当前生命"] = self.target["生命值"]
            return True
        if name == "设结算目标生命":
            if self.target is not None and isinstance(args[0], (int, float)):
                self.target["生命值"] = float(args[0])
            return True
        if name.startswith("设") and args:
            self.var[name[1:]] = args[0]
            return True
        if name in ("挂载效果", "移除效果", "移除同效果", "写入快照", "执行到期动作", "执行过量转盾", "转移效果", "选取可驱散效果"):
            return self._status_call(name, args)
        if name in ("有同效果", "有可驱散效果", "匹配驱散类型", "结算目标递减系数"):
            return self._status_query(name, args)
        self._missing(name)
        return False

    def _effect(self, args):
        label = str(args[0])
        leech_flag = self.skill.get("计入吸血") if isinstance(self.skill, dict) else getattr(self.skill, "leech", None)
        reflect_flag = self.skill.get("计入反伤") if isinstance(self.skill, dict) else getattr(self.skill, "reflect", None)
        if label == "物理吸血效果" and leech_flag != "是":
            return 0
        if label == "魔法吸血效果" and leech_flag != "是":
            return 0
        if label == "物理反伤效果" and reflect_flag != "是":
            return 0
        if label == "魔法反伤效果" and reflect_flag != "是":
            return 0
        side = str(args[1]) if len(args) > 1 else None
        env = dict(self.env)
        env["攻方"] = _stats(self.atk)
        env["守方"] = _stats(self.dfd)
        env["攻方等级"] = _stats(self.atk).get("等级")
        env["防方等级"] = _stats(self.dfd).get("等级")
        if side == "攻方":
            env["守方"] = _stats(self.atk)
        value = self.curves.effect(label, env)
        if isinstance(value, (int, float)):
            value = _fold_modifiers(value, label, self.dfd)
        return 0 if value is None else value

    def _status_call(self, name: str, args: list):
        unit = self.target
        if unit is None:
            return False
        if name == "挂载效果":
            effect = self.env.get("效果行") or {}
            stacks = self.var.get("异常层数")
            if not isinstance(stacks, (int, float)):
                stacks = 1
            remain = self.var.get("剩余时长")
            if not isinstance(remain, (int, float)):
                remain = effect.get("效果时间")
            mutex = str(self.env.get("互斥组") or effect.get("互斥组") or "").strip()
            if mutex:
                kept = []
                for item in unit.get("效果实例", []):
                    row = item.get("行") or {}
                    other = str(row.get("互斥组") or "").strip()
                    if other and other == mutex and item.get("效果名") != effect.get("效果名"):
                        continue
                    kept.append(item)
                unit["效果实例"] = kept
            existing = next((item for item in unit.get("效果实例", []) if item.get("效果名") == effect.get("效果名")), None)
            if existing and str(self.var.get("叠加规则") or "") == "叠层":
                existing["层数"] = stacks
                existing["剩余"] = remain
                return True
            if existing and str(self.var.get("刷新规则") or self.env.get("刷新规则") or "") in ("刷新", "重置", "刷新时长"):
                existing["剩余"] = remain
                existing["层数"] = stacks if str(self.var.get("叠加规则") or "") == "叠层" else existing.get("层数", stacks)
                return True
            unit.setdefault("效果实例", []).append({
                "效果名": effect.get("效果名"),
                "层数": stacks,
                "剩余": remain,
                "行": effect,
            })
            return True
        if name == "移除效果" or name == "移除同效果":
            code = str(args[0]) if args else ""
            unit["效果实例"] = [item for item in unit.get("效果实例", []) if item.get("效果名") != code]
            return True
        if name == "执行过量转盾":
            amount = args[0] if args else self.var.get("过量治疗") or 0
            if isinstance(amount, (int, float)) and amount > 0:
                unit.setdefault("护盾层", []).append({"类型": "全部", "剩余": float(amount)})
            return True
        return True

    def _status_query(self, name: str, args: list):
        unit = self.target
        if name == "有同效果":
            code = str(args[0]) if args else str(self.env.get("效果代号") or "")
            return any(item.get("效果名") == code for item in (unit or {}).get("效果实例", []))
        if name == "有可驱散效果":
            return any(item.get("行", {}).get("驱散类型") for item in (unit or {}).get("效果实例", []))
        if name == "匹配驱散类型":
            return True
        if name == "结算目标递减系数":
            return 1
        return False

    def _missing(self, name: str) -> None:
        if name in self._seen_calls:
            return
        self._seen_calls.add(name)
        text = f"战斗流程函数「{name}」还没有实现，这一步按失败处理"
        if text not in self.gaps:
            self.gaps.append(text)

    def _land(self, steps, index, order, pos, target):
        """步骤序对得上就跳过去。对不上时，落到仍存在的、序号更大的下一步。

        往回跳只留给名字里带「继续」的循环。指向自己的跳转改成顺序执行，避免死循环。
        """
        if target in index:
            return index[target]
        higher = [i for i, number in enumerate(order) if number > target]
        if not higher:
            return pos + 1
        succ = higher[0]
        name = str(steps[pos].get("步骤名") or "")
        if succ == pos or (succ < pos and "继续" not in name):
            return pos + 1
        return succ

    def run(self, pipe: str) -> None:
        steps = self.pipes.get(pipe) or []
        if not steps:
            text = f"战斗流程没有「{pipe}」的步骤"
            if text not in self.gaps and pipe not in ("状态施加",):
                # 施法步骤会进入「状态施加」，表上的块名是「状态」。
                alias = {"状态施加": "状态", "伤害": "伤害", "治疗": "治疗"}.get(pipe)
                if alias and alias in self.pipes and alias != pipe:
                    self.run(alias)
                    return
                if pipe not in self.pipes:
                    self.gaps.append(text)
            return
        order = [step["步骤序"] for step in steps]
        index = {number: pos for pos, number in enumerate(order)}
        pos = 0
        guard = 0
        while 0 <= pos < len(order) and guard < 400:
            guard += 1
            step = steps[pos]
            value = evaluate(str(step.get("判定公式") or ""), self)
            jump = step.get("成功跳转") if _ok(value) else step.get("失败跳转")
            if jump in (None, "", 0, "0"):
                pos += 1
                continue
            try:
                target = int(float(jump))
            except (TypeError, ValueError):
                pos += 1
                continue
            if target == -1:
                break
            pos = self._land(steps, index, order, pos, target)


def _ok(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    return bool(value)


def _stats(unit) -> dict:
    if unit is None:
        return {}
    attrs = unit.get("属性")
    if hasattr(attrs, "as_dict"):
        data = attrs.as_dict()
    else:
        data = dict(attrs or {})
    data["等级"] = data.get("等级", unit.get("等级"))
    return data


def _fold_modifiers(value: float, label: str, defender) -> float:
    if defender is None or label not in ("易损效果", "伤害效果"):
        return value
    for effect in defender.get("效果实例") or []:
        row = effect.get("行") or {}
        if row.get("伤害修正1阶段") == "承伤" and row.get("伤害修正1方向") == "受到" and row.get("伤害修正1运算") == "乘":
            try:
                value *= float(row.get("伤害修正1数值"))
            except (TypeError, ValueError):
                pass
    return value


def load_pipelines(path: str) -> dict[str, list[dict]]:
    rows = read_sheet(path, "战斗流程", max_row=140)
    titles = rows.get(2, {})
    headers = rows.get(3, {})
    blocks = []
    current = None
    start = None
    last = 0
    for col in sorted(set(titles) | set(headers)):
        if col in titles:
            if current:
                blocks.append((current, start, col - 1))
            current = titles[col]
            start = col
        last = col
    if current:
        blocks.append((current, start, last))
    pipes = {}
    for name, left, right in blocks:
        header = {headers[col]: col for col in range(left, right + 1) if col in headers}
        if "步骤序" not in header or "判定公式" not in header:
            continue
        steps = []
        for index in range(8, 140):
            cells = rows.get(index, {})
            title = cells.get(header["步骤名"]) if "步骤名" in header else None
            if not title:
                continue
            step = {field: cells.get(col) for field, col in header.items() if col in cells}
            try:
                step["步骤序"] = int(float(step.get("步骤序")))
            except (TypeError, ValueError):
                continue
            for key in ("成功跳转", "失败跳转"):
                if key in step:
                    try:
                        step[key] = int(float(step[key]))
                    except (TypeError, ValueError):
                        step[key] = 0
            steps.append(step)
        # 叠层已经写好层数之后，刷新失败不能再掉进取强，否则会被「无同效果」把层数盖回 1。
        for step in steps:
            if step.get("步骤名") == "【叠层】判定叠加刷新" and step.get("失败跳转") == 24:
                step["失败跳转"] = 34
        if steps:
            pipes[name] = steps
    return pipes
