"""把技能、效果、场景上已经填写的格子收成战斗要用的结构。没有格子就不产生字段。"""
from __future__ import annotations


def _num(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _text(value):
    if value in (None, ""):
        return None
    return str(value).strip()


class SkillSpec:
    def __init__(self, row: dict, gaps: list[str]):
        self.row = row
        self.name = _text(row.get("技能名"))
        self.level = _num(row.get("技能等级"))
        self.max_level = _num(row.get("最大等级"))
        self.kind = _text(row.get("技能类型"))
        self.owner_kind = _text(row.get("归属类型"))
        self.owner = _text(row.get("归属者"))
        self.skill_id = _text(row.get("技能ID"))
        self.weapon = _text(row.get("武器归属"))
        self.tags = _text(row.get("技能标签"))
        self.need_target = _text(row.get("需要目标"))
        self.min_range = _num(row.get("最小距离"))
        self.max_range = _num(row.get("最大距离"))
        self.resource = _text(row.get("主消耗资源"))
        self.cost = _num(row.get("主消耗量"))
        self.pay_at = _text(row.get("主消耗时机"))
        self.refund_resource = _text(row.get("回复资源"))
        self.refund = _num(row.get("回复量"))
        self.refund_at = _text(row.get("回复时机"))
        self.cooldown = _num(row.get("冷却时间"))
        self.gcd = _num(row.get("公共冷却时长"))
        self.chant = _num(row.get("吟唱时长"))
        self.action = _num(row.get("动作时长"))
        self.channel = _num(row.get("引导时长"))
        self.channel_ticks = _num(row.get("引导跳数"))
        self.repeat = _num(row.get("连发次数"))
        self.repeat_gap = _num(row.get("连发间隔"))
        self.interruptible = _text(row.get("可被打断"))
        self.hurt_interrupt = _text(row.get("受伤打断"))
        self.move_cast = _text(row.get("可移动施法"))
        self.camp = _text(row.get("过滤阵营"))
        self.pick = _text(row.get("选择规则"))
        self.target_cap = _num(row.get("目标数量上限"))
        self.splash = _num(row.get("溅射半径"))
        self.value_type = _text(row.get("数值类型"))
        self.element_from = _text(row.get("元素来源"))
        self.element = _text(row.get("元素"))
        self.formula = row.get("数值解析式")
        self.segments = _num(row.get("伤害段数"))
        self.segment_gap = _num(row.get("伤害段间隔"))
        self.separate_rolls = _text(row.get("段独立判定"))
        self.hit_rule = _text(row.get("命中规则"))
        self.block_rule = _text(row.get("格挡规则"))
        self.crit_rule = _text(row.get("暴击规则"))
        self.use_element = _text(row.get("参与元素克制"))
        self.use_size = _text(row.get("参与体型克制"))
        self.leech = _text(row.get("计入吸血"))
        self.reflect = _text(row.get("计入反伤"))
        self.heal_formula = row.get("治疗数值解析式")
        self.heal_pick = _text(row.get("治疗目标规则"))
        self.heal_segments = _num(row.get("治疗段数"))
        self.duration = _num(row.get("技能持续时间"))
        self.dash_mode = _text(row.get("自身位移方式"))
        self.dash_distance = _num(row.get("自身位移距离"))
        self.dash_speed = _num(row.get("自身位移速度"))
        self.interrupt_level = _num(row.get("打断目标等级"))
        self.summon = _text(row.get("召唤物"))
        self.summon_count = _num(row.get("召唤数量"))
        self.summon_time = _num(row.get("召唤持续时间"))
        self.summon_scale = _num(row.get("属性继承比例"))
        self.threat = _num(row.get("伤害仇恨系数"))
        self.intent = _text(row.get("意图类别"))
        self.value_kind = _text(row.get("价值口径"))
        self.priority = _num(row.get("择技基线优先级"))
        self.expected_targets = _num(row.get("预期目标数"))
        self.effects = []
        for index in range(1, 7):
            name = _text(row.get(f"施加效果{index}"))
            if not name:
                continue
            self.effects.append({
                "效果": name,
                "时机": _text(row.get(f"施加效果{index}时机")),
                "概率": _num(row.get(f"施加效果{index}概率%")),
                "层数": _num(row.get(f"施加效果{index}层数")),
                "延迟": _num(row.get(f"施加效果{index}延迟")),
                "目标": _text(row.get(f"施加效果{index}目标")),
            })
        known = _KNOWN_SKILL
        for key in row:
            if key not in known:
                text = f"技能「{self.name}」的「{key}」有值，但结算还没有读取这一列"
                if text not in gaps:
                    gaps.append(text)


_KNOWN_SKILL = {
    "技能名", "技能等级", "最大等级", "技能类型", "归属类型", "归属者", "技能ID", "武器归属", "技能标签",
    "需要目标", "最小距离", "最大距离", "主消耗资源", "主消耗量", "主消耗时机", "回复资源", "回复量", "回复时机",
    "冷却时间", "公共冷却时长", "吟唱时长", "动作时长", "引导时长", "引导跳数", "连发次数", "连发间隔", "可移动施法",
    "可被打断", "受伤打断",
    "过滤阵营", "选择规则", "目标数量上限", "溅射半径", "数值类型", "元素来源", "元素", "数值解析式", "伤害段数",
    "伤害段间隔", "段独立判定", "命中规则", "格挡规则", "暴击规则", "参与元素克制", "参与体型克制", "计入吸血", "计入反伤",
    "治疗数值解析式", "治疗目标规则", "治疗段数", "技能持续时间", "自身位移方式", "自身位移距离", "自身位移速度",
    "打断目标等级", "召唤物", "召唤数量", "召唤持续时间", "属性继承比例", "伤害仇恨系数",
    "意图类别", "价值口径", "择技基线优先级", "预期目标数",
}
for _i in range(1, 7):
    for _suffix in ("", "时机", "概率%", "层数", "延迟", "目标"):
        _KNOWN_SKILL.add(f"施加效果{_i}{_suffix}")


class EffectSpec:
    def __init__(self, row: dict, gaps: list[str]):
        self.row = row
        self.name = _text(row.get("效果名"))
        self.level = _num(row.get("效果等级"))
        self.max_level = _num(row.get("最大等级"))
        self.kind = _text(row.get("效果类型"))
        self.direction = _text(row.get("结算方向"))
        self.owner_kind = _text(row.get("归属类型"))
        self.value_type = _text(row.get("数值类型"))
        self.element_from = _text(row.get("元素来源"))
        self.element = _text(row.get("元素"))
        self.formula = row.get("数值解析式")
        self.duration = _num(row.get("效果时间"))
        self.tick = _num(row.get("跳动间隔"))
        self.tick_now = _text(row.get("首跳即时"))
        self.max_stacks = _num(row.get("最大层数"))
        self.stack_rule = _text(row.get("叠加规则"))
        self.refresh = _text(row.get("刷新规则"))
        self.mutex = _text(row.get("互斥组"))
        self.remove_count = _num(row.get("移除计数"))
        self.expire = _text(row.get("到期动作"))
        self.dispel = _text(row.get("驱散类型"))
        self.control = _text(row.get("控制类别"))
        self.control_act = _text(row.get("控制行为"))
        self.mark = _text(row.get("状态标记"))
        self.mods = []
        for index in (1, 2, 3):
            stat = _text(row.get(f"属性修正{index}属性"))
            if not stat:
                continue
            self.mods.append((stat, _text(row.get(f"属性修正{index}运算")), _num(row.get(f"属性修正{index}数值"))))
        self.damage_stage = _text(row.get("伤害修正1阶段"))
        self.damage_dir = _text(row.get("伤害修正1方向"))
        self.damage_op = _text(row.get("伤害修正1运算"))
        self.damage_value = _num(row.get("伤害修正1数值"))
        self.shield = row.get("护盾吸收量")
        self.shield_type = _text(row.get("护盾吸收类型"))
        self.split = _num(row.get("伤害分摊比例"))
        self.unselectable = _text(row.get("不可选中"))
        self.rewrite_tag = _text(row.get("改写技能标签"))
        self.rewrite_field = _text(row.get("改写字段"))
        self.rewrite_op = _text(row.get("改写运算"))
        self.rewrite_value = _num(row.get("改写数值"))
        self.shape = _text(row.get("范围形状"))
        self.radius = _num(row.get("范围半径"))
        self.zone_camp = _text(row.get("范围作用阵营"))
        self.intent = _text(row.get("意图类别"))
        self.value_kind = _text(row.get("价值口径"))
        known = _KNOWN_EFFECT
        for key in row:
            if key not in known:
                text = f"效果「{self.name}」的「{key}」有值，但结算还没有读取这一列"
                if text not in gaps:
                    gaps.append(text)


_KNOWN_EFFECT = {
    "效果名", "效果等级", "最大等级", "效果类型", "结算方向", "归属类型", "归属者", "效果ID", "效果标签",
    "数值类型", "元素来源", "元素", "数值解析式", "命中规则", "格挡规则", "暴击规则", "段独立判定",
    "效果时间", "是否永久", "时长受缩短", "跳动间隔", "跳动受缩短", "首跳即时", "不完整跳",
    "快照时机", "快照属性列表", "最大层数", "可叠加来源", "叠加规则", "刷新规则", "刷新补时比例%",
    "时长继承%", "层衰减间隔", "层衰减数量", "到期减层", "层数值缩放", "互斥组",
    "结算时机", "事件监听", "结算条件", "触发概率%", "内置冷却", "每层独立触发", "触发技能", "触发技能概率%",
    "额外效果1", "额外效果1层数", "额外效果2", "额外效果2层数",
    "移除条件", "移除计数", "到期动作", "关联移除效果", "死亡不移除", "可窃取转移",
    "驱散类型", "驱散优先级", "控制类别", "控制行为", "状态标记", "破控比例", "控制递减组", "递减系数",
    "首领抗性", "被控制暂停跳动",
    "属性修正1属性", "属性修正1运算", "属性修正1数值", "属性修正2属性", "属性修正2运算", "属性修正2数值",
    "属性修正3属性", "属性修正3运算", "属性修正3数值",
    "伤害修正1阶段", "伤害修正1方向", "伤害修正1运算", "伤害修正1数值",
    "伤害修正2阶段", "伤害修正2方向", "伤害修正2运算", "伤害修正2数值", "修正作用标签",
    "护盾吸收量", "护盾吸收类型", "护盾优先级", "护盾组", "护盾次数", "免疫数值类型", "伤害分摊比例",
    "致死保护生命值%", "替换技能", "禁用技能", "改写技能",
    "不可选中", "改写技能标签", "改写字段", "改写运算", "改写数值", "仇恨修正",
    "范围形状", "范围半径", "范围内径", "范围角度", "范围高度", "范围长度", "范围宽度",
    "范围原点", "范围随挂载移动", "范围扩张速度", "范围作用阵营", "范围朝向", "范围目标上限",
    "拦截次数", "拦截类型", "拦截消耗方式", "拦截生命值系数",
    "占格组", "占格策略", "占格优先级", "实体生命值", "实体可攻击", "实体可驱散",
    "意图类别", "价值口径",
}


def compile_specs(contract: dict) -> None:
    gaps = contract.setdefault("待对齐", [])
    contract["skill_specs"] = {name: SkillSpec(row, gaps) for name, row in contract["skills"].items()}
    contract["effect_specs"] = {name: EffectSpec(row, gaps) for name, row in contract["effects"].items()}
