# -*- coding: utf-8 -*-
"""战斗流程判定公式 — 中文标准 DSL 语法约定与校验。

权威约定见 ``战斗模拟/文档/战斗流程标准语法.md``。
属性引用（效果 / 攻方 / 守方 / 结算目标属性）的用途名必须存在于「属性总表」列 B。
效果() 可一参（攻守对抗默认）或两参 效果(用途名,攻方|守方) 绑定求值面板。

2026-09-15：6 管线（伤害/治疗/效果事件 × PVE/PVP；效果事件含驱散/偷取）；快照+层衰减；禁止 调用结算。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# 管线局部标识符（非属性总表）
# ---------------------------------------------------------------------------
管线局部标识符: frozenset[str] = frozenset(
    {
        "管线伤害",
        "基础伤害",
        "吟唱时长",
        "最终伤害",
        "治疗值",
        "治疗量",
        "基础治疗",
        "格挡减免量",
        "反伤量",
        "吸血量",
        "仇恨系数",
        "仇恨基础比例",
        "模式",
        "伤害类型",
        "伤害来源",
        "治疗来源",
        "当前生命",
        "结算伤害",
        "结算目标",
        "结算目标生命",
        "护盾吸收量",
        "护盾游标",
        "护盾层数",
        "当前护盾",
        "本层吸收",
        "过量伤害",
        "本次破盾数",
        "生命空档",
        "实际治疗",
        "溢出治疗",
        "过量治疗",
        "过量转盾量",
        "治疗吸收量",
        "治疗吸收游标",
        "治疗吸收层数",
        "当前治疗吸收",
        "本层治疗吸收",
        "破盾结束Buff列表",
        "对应吸血",
        "对应反伤",
        "实际扣血",
        "实际反伤扣血",
        "伤害仇恨",
        "治疗仇恨",
        # 效果事件管线上下文（局部标识仍用异常*字段名）
        "异常挂载结果",
        "异常层数",
        "剩余时长",
        "基础时长",
        "基础层数",
        "最大层数",
        "当前层数",
        "附着概率",
        "效果代号",
        "效果类型",
        "叠加规则",
        "刷新规则",
        "时长继承",
        "跳动间隔",
        "生效时机",
        "互斥组",
        "控制递减组",
        "递减系数",
        "控制行为",
        "命中位",
        "暴击位",
        "首领抗性",
        "数值类型",
        "异常跳伤基础",
        "异常跳疗基础",
        "跳伤伤害",
        "跳疗治疗",
        "旧强度",
        "新强度",
        "PVP时长系数",
        "叠加动作",
        "标签",
        # 快照 / 层衰减
        "快照时机",
        "快照属性列表",
        "层衰减间隔",
        "层衰减数量",
        # 驱散管线
        "驱散结果",
        "已驱散数",
        "驱散强度",
        "驱散类型",
        "驱散优先级",
        "驱散类型等级",
        "可窃取",
        "到期动作",
        "触发结果",
        "触发概率",
        "通知结果",
    }
)

# 布尔字面量（禁止单独作为步骤整式终端；校验器仍识别以便组合表达式）
布尔字面量: frozenset[str] = frozenset({"真", "假"})

# 伤害类型字面量 / 标记枚举 / 状态枚举
伤害类型字面量: frozenset[str] = frozenset({"物理", "魔法"})
标记枚举: frozenset[str] = frozenset(
    {
        "已闪避",
        "已暴击",
        "已格挡",
        "已死亡",
        "已破盾",
        "结算伤害已注入",
        "攻方已死亡",
        "反伤扣血中",
        "过量转盾开启",
        "锁1血",
        "不死",
        "必中",
        "不可暴击",
        "需立即跳转",
        "施法中",
        "请求状态管线",
        "异常跳转结算",
        "请求伤害管线",
        "请求治疗管线",
        "异常到期结算",
        "首领",
        "层衰减结算",
        "强驱",
        "可窃取技能",
    }
)
状态枚举: frozenset[str] = frozenset(
    {
        "无敌",  # MMO 泛无敌（与物/魔免疫并列）
        "锁1血",  # MMO 免死雏形
        "不死",
        "免疫物理",  # UGit IMMUNE_PHYSICAL
        "免疫魔法",  # UGit IMMUNE_MAGIC
        "必定闪避",
        "绝对回避",
        "禁止受疗",
        "无法被治疗",
        "效果免疫",
        "控制免疫",
    }
)
角色枚举: frozenset[str] = frozenset({"攻方", "守方"})  # 效果() 第二参 / 设结算目标
效果类型字面量: frozenset[str] = frozenset(
    {"增益", "减益", "控制", "标记", "形态", "隐身", "护盾", "即时", "区域", "治疗"}
)
叠加规则字面量: frozenset[str] = frozenset(
    {"独立", "叠层", "刷新", "替换", "取强", "取弱"}
)
刷新规则字面量: frozenset[str] = frozenset({"继承刷新", "重置刷新"})
命中位字面量: frozenset[str] = frozenset({"必中", "命中判定"})
暴击位字面量: frozenset[str] = frozenset({"不可暴击", "可暴击"})
伤害来源字面量: frozenset[str] = frozenset({"持续", "直接", "技能"})
治疗来源字面量: frozenset[str] = frozenset({"持续", "直接", "技能"})
生效时机字面量: frozenset[str] = frozenset({"立即", "延迟"})
数值类型字面量: frozenset[str] = frozenset({"物理", "魔法", "治疗", "无"})
空字面量: frozenset[str] = frozenset({"空"})
模式字面量: frozenset[str] = frozenset({"PVE", "PVP", "副本", "战场"})
是否字面量: frozenset[str] = frozenset({"是", "否"})
快照时机字面量: frozenset[str] = frozenset({"施加时", "每跳动", "无"})
驱散类型等级字面量: frozenset[str] = frozenset({"可驱散", "仅强驱", "不可驱散"})
驱散通道字面量: frozenset[str] = frozenset({"魔法", "诅咒", "毒", "疾病", "物理", "无"})
管线名枚举: frozenset[str] = frozenset(
    {
        "伤害PVE",
        "伤害PVP",
        "治疗PVE",
        "治疗PVP",
        "状态PVE",
        "状态PVP",
        "效果事件PVE",
        "效果事件PVP",
    }
)
规划管线名: frozenset[str] = frozenset(
    {
        "伤害",
        "治疗",
        "状态施加",
        "伤害PVE",
        "伤害PVP",
        "治疗PVE",
        "治疗PVP",
        "状态PVE",
        "状态PVP",
        "伤害环境",
        "伤害对战",
        "治疗环境",
        "治疗对战",
        "状态环境",
        "状态对战",
        "特殊事件",
        "施法",
        "周期跳动",
        "效果存续",
        "驱散与偷取",
        "效果触发",
        "引擎通知",
    }
)
# 短期兼容：旧管线标识 → 新名（表与主文档用新名；驱散并入效果事件）
管线名别名: dict[str, str] = {
    "效果事件PVE": "状态PVE",
    "效果事件PVP": "状态PVP",
    "异常PVE": "状态PVE",
    "异常PVP": "状态PVP",
    "驱散PVE": "状态PVE",
    "驱散PVP": "状态PVP",
}


def 规范化管线名(name: str) -> str:
    """将旧管线标识映射到现行名；未知名原样返回。"""
    return 管线名别名.get(str(name), str(name))

# 无参 / 有参函数名（不含效果/攻方/守方，单独校验属性）
无参函数: frozenset[str] = frozenset({"随机", "有可驱散效果"})
设值函数: frozenset[str] = frozenset(
    {
        "设管线伤害",
        "设最终伤害",
        "设治疗值",
        "设治疗量",
        "设吸血量",
        "设反伤量",
        "设格挡减免量",
        "设伤害仇恨",
        "设治疗仇恨",
        "设当前生命",
        "设结算伤害",
        "设结算目标",
        "设结算目标生命",
        "设护盾吸收量",
        "设护盾游标",
        "设当前护盾",
        "设本层吸收",
        "设过量伤害",
        "设生命空档",
        "设实际治疗",
        "设溢出治疗",
        "设过量治疗",
        "设过量转盾量",
        "设治疗吸收量",
        "设治疗吸收游标",
        "设当前治疗吸收",
        "设本层治疗吸收",
        "设对应吸血",
        "设对应反伤",
        "设实际扣血",
        "设实际反伤扣血",
        "设异常挂载结果",
        "设异常层数",
        "设剩余时长",
        "设基础时长",
        "设跳伤伤害",
        "设跳疗治疗",
        "设叠加动作",
        "设伤害类型",
        "设伤害来源",
        "设治疗来源",
        "设驱散结果",
        "设已驱散数",
        "设驱散强度",
        "设驱散类型",
        "设驱散优先级",
        "设触发结果",
        "设通知结果",
        "设吟唱时长",
    }
)
二元数值函数: frozenset[str] = frozenset({"最大", "最小"})  # 最大(a,b) / 最小(a,b)
三元数值函数: frozenset[str] = frozenset({"钳制"})  # 钳制(x,lo,hi)
属性取用函数: frozenset[str] = frozenset({"效果", "攻方", "守方", "结算目标属性"})
标记函数: frozenset[str] = frozenset({"标记"})
取消标记函数: frozenset[str] = frozenset({"取消标记"})
进入管线函数: frozenset[str] = frozenset({"进入管线"})
有标记函数: frozenset[str] = frozenset({"有标记"})
没有标记函数: frozenset[str] = frozenset({"没有标记"})
没有状态函数: frozenset[str] = frozenset({"没有状态"})
异常函数: frozenset[str] = frozenset(
    {
        "效果标签被免疫",
        "互斥组冲突",
        "移除互斥组效果",
        "移除同效果",
        "有同效果",
        "挂载效果",
        "结算目标递减系数",
        "写入快照",
    }
)
驱散函数: frozenset[str] = frozenset(
    {
        "选取可驱散效果",
        "匹配驱散类型",
        "移除效果",
        "转移效果",
        "执行到期动作",
    }
)
# 总分总后禁止调用结算（扣血/回血块已删，settle 内联）
调用结算函数: frozenset[str] = frozenset({"调用结算"})
结算目标枚举: frozenset[str] = frozenset()  # 空：任何 调用结算 均拒
状态函数: frozenset[str] = frozenset({"有状态", "结算目标有状态"})
结算目标标记函数: frozenset[str] = frozenset({"结算目标有标记"})
护盾函数: frozenset[str] = frozenset(
    {
        "护盾吸收",
        "取护盾层",
        "护盾类型可吸收",
        "护盾剩余容量",
        "扣减护盾层",
        "取治疗吸收层",
        "治疗吸收剩余容量",
        "扣减治疗吸收层",
        "生成治疗吸收",
        "生成护盾",
        "执行过量转盾",
    }
)

# 步骤名白名单（稳定中文 opcode）
规范化步骤名: frozenset[str] = frozenset(
    {
        "【叠层】保持当前层数",
        "【叠层】允许并列挂载",
        "【叠层】判定取弱保持旧",
        "【叠层】判定取强保持旧",
        "【叠层】判定叠加刷新",
        "【叠层】判定叠加取弱",
        "【叠层】判定叠加取强",
        "【叠层】判定叠加叠层",
        "【叠层】判定叠加替换",
        "【叠层】判定叠加独立",
        "【叠层】判定已有同效果",
        "【叠层】判定继承刷新",
        "【叠层】应用叠层",
        "【叠层】应用继承时长",
        "【叠层】应用重置时长",
        "【叠层】无同效果设层数",
        "【叠层】无同效果设时长",
        "【叠层】替换设层数",
        "【叠层】移除旧效果",
        "【叠层】重置剩余时长",
        "【命中】判定附着概率失败",
        "【命中】判定需要控制命中",
        "【命中】控制命中判定",
        "【命中】标记未命中",
        "【拒绝】判定互斥组冲突",
        "【拒绝】判定目标免疫该效果",
        "【拒绝】判定目标已死亡",
        "【拒绝】判定首领抗性拒绝",
        "【持续】清零反伤量",
        "【持续】清零吸血量",
        "【持续】结算前清零反伤",
        "【持续】结算前清零吸血",
        "【持续】跳过闪避格挡",
        "【挂载】写入异常挂载",
        "【挂载】判定立即跳转",
        "【挂载】应用PVP时长系数",
        "【挂载】标记需立即跳转",
        "【跳转】判定跳伤",
        "【跳转】判定跳疗",
        "【跳转】判定跳转结算入口",
        "【递减】判定控制递减",
        "【递减】应用递减时长",
        "伤害收束",
        "伤害管线收束",
        "伤害结束",
        "保持管线伤害",
        "写入伤害仇恨",
        "写入治疗仇恨",
        "写入物理对应反伤",
        "写入物理对应吸血",
        "写入魔法对应反伤",
        "写入魔法对应吸血",
        "写出伤害仇恨",
        "写出伤害管线结果",
        "写出异常挂载成功",
        "写出异常未挂载",
        "写出异常未挂载终端",
        "写出异常跳转未结算",
        "写出最终伤害",
        "写出治疗仇恨",
        "写出治疗管线结果",
        "写出跳伤请求",
        "写出跳疗请求",
        "初始化伤害",
        "初始化异常结果",
        "初始化护盾吸收量",
        "初始化护盾游标",
        "初始化治疗吸收量",
        "初始化治疗吸收游标",
        "初始化治疗",
        "初始化结算伤害",
        "判定不可暴击",
        "判定克制",
        "判定反伤",
        "判定反伤扣血中",
        "判定吸血",
        "判定回血目标已死亡",
        "判定已闪避",
        "判定必中",
        "判定持续伤害来源",
        "判定持续跳过吸血反伤",
        "判定持续跳过格挡",
        "判定攻方已死亡",
        "判定无敌",
        "判定暴击",
        "判定本层可吸收",
        "判定本次破盾",
        "判定格挡",
        "判定死亡",
        "判定死亡目标为守方",
        "判定治疗仇恨",
        "判定治疗暴击",
        "判定物理伤害",
        "判定物理通道",
        "判定破盾",
        "判定禁疗",
        "判定结算伤害已注入",
        "判定结算目标为守方",
        "判定结算目标无敌",
        "判定结算目标免疫或无敌",
        "判定过量转盾",
        "判定过量转盾(非UGit预留)",
        "判定锁1血",
        "判定还有护盾可吸收",
        "判定还有治疗吸收",
        "判定本层治疗吸收存活",
        "判定闪避",
        "判定零伤或闪避短路",
        "判定零伤短路",
        "判定零治疗短路",
        "判定魔法伤害",
        "判定魔法通道",
        "取当前层护盾",
        "取当前层治疗吸收",
        "受疗方执行回血",
        "同步结算目标生命",
        "吸血回血收束",
        "回血收束",
        "因死亡跳过仇恨",
        "夹断实际治疗",
        "夹断扣血量",
        "夹断结算伤害",
        "守方执行扣血",
        "应用克制",
        "应用受治疗",
        "应用施法治疗",
        "应用暴击伤害",
        "应用格挡",
        "应用治疗暴击",
        "应用物理免伤与物理伤害效果",
        "应用物理通道",
        "应用魔法免伤与魔法伤害效果",
        "应用魔法通道",
        "扣减本层护盾",
        "扣减本层治疗吸收",
        "扣减结算伤害",
        "扣减治疗量",
        "扣血收束",
        "扣血段收束",
        "执行吸血回血",
        "执行回血",
        "执行扣生命",
        "执行扣血",
        "执行护盾吸收",
        "护盾游标前进",
        "治疗吸收游标前进",
        "拒绝吸血回血",
        "拒绝回血",
        "攻方执行反伤扣血",
        "攻方执行吸血回血",
        "无敌清零护盾吸收",
        "无敌清零结算",
        "无敌清零结算伤害",
        "最终伤害夹断非负",
        "未暴击收束",
        "标记反伤扣血中",
        "标记守方死亡",
        "标记攻方死亡",
        "标记暴击",
        "标记死亡",
        "标记破盾",
        "标记闪避",
        "治疗收束",
        "治疗管线收束",
        "治疗结束",
        "治疗编排收束",
        "注入反伤结算伤害",
        "注入结算伤害",
        "清除反伤标记",
        "清除攻方死亡标记",
        "清除暴击标记",
        "清除死亡标记",
        "清除破盾标记",
        "清除闪避标记",
        "清零伤害仇恨",
        "清零反伤量",
        "清零吸血量",
        "清零实际扣血",
        "清零治疗仇恨",
        "移除互斥效果",
        "类型不匹配游标前进",
        "累加护盾吸收",
        "累加治疗吸收",
        "结算溢出伤害",
        "结算编排收束",
        "计算伤害仇恨",
        "计算反伤量",
        "计算吸血反伤",
        "计算吸血量",
        "计算实际治疗",
        "计算本层吸收",
        "计算本层治疗吸收",
        "计算治疗仇恨",
        "计算溢出治疗",
        "计算生命空档",
        "记录实际反伤扣血",
        "记录实际扣血",
        "记录格挡减免",
        "记录过量伤害",
        "记录过量治疗",
        "设反伤结算目标攻方",
        "设回血结算目标攻方",
        "设治疗量",
        "设治疗量为吸血",
        "设结算目标守方",
        "跳过仇恨收束",
        "过量转化护盾",
        "过量转化护盾(非UGit预留)",
        "应用锁1血",
        "无敌清零吸血量",
        "无敌清零反伤量",
        "免疫清零结算伤害",
        "闪避清零伤害",
        "零伤清零伤害仇恨",
        "零治疗写出",
        # 快照 / 层衰减
        "【快照】判定施加时快照",
        "【快照】写入快照",
        "【层衰减】判定层衰减入口",
        "【层衰减】判定间隔有效",
        "【层衰减】减层",
        "【层衰减】判定层耗尽",
        "【层衰减】移除效果",
        "【层衰减】收束",
        # 驱散*
        "初始化驱散结果",
        "初始化已驱散数",
        "【预处理】夹断驱散强度",
        "【预处理】同步驱散类型",
        "【预处理】同步驱散优先级基准",
        "【预处理】判定零强度短路",
        "【选取】判定驱散额度剩余",
        "【选取】判定有可驱散效果",
        "【选取】按优先级选取",
        "【选取】匹配驱散类型",
        "【选取】判定首领抗性门",
        "【选取】判定效果不可驱散",
        "【选取】判定仅强驱需强驱标记",
        "【选取】强驱标记门",
        "【执行】判定可窃取转移",
        "【执行】转移效果",
        "【执行】移除效果",
        "【连锁】判定到期动作",
        "【连锁】执行到期动作",
        "【连锁】累加已驱散数",
        "【连锁】回写中间驱散结果",
        "【连锁】继续选取下一效果",
        "写出驱散结果",
        "【持续】跳过闪避判定",
        "零伤短路收束",
        "【跳转】标记持续伤害来源",
        "【跳转】标记持续治疗来源",
        "【到期】判定到期入口",
        "【到期】判定有到期动作",
        "【到期】执行到期动作",
        "【到期】移除效果",
        "【到期】收束",
        "驱散结果",
    }
)

# 残留英文 Aviator（出现即拒）
_BANNED_ENGLISH = (
    "setPipelineDamage",
    "pipelineDamage",
    "formulaParam",
    "isPhysicalDamage",
    "isMagicalDamage",
    "setDodged",
    "setCritical",
    "setBlockValue",
    "blockValue",
    "casterAttr",
    "targetAttr",
    "setLifestealValue",
    "setReflectDamage",
    "finalDamage",
    "setHeal",
    "setDamageThreat",
    "setHealThreat",
    "threatCoef",
    "reflectDamage",
    "damageContext",
    "random()",
    "clamp(",
    "HealBonus",
    "AllDmgBonus",
)

# 标识符：中文 / 字母 / 数字 / _ / % （属性名可含这些；括号在取用参数中单独切）
_IDENT_RE = re.compile(
    r"[\u4e00-\u9fffA-Za-z_][\u4e00-\u9fffA-Za-z0-9_%]*"
)

# 兼容旧导出名
允许的函数前缀 = (
    无参函数
    | 设值函数
    | 二元数值函数
    | 三元数值函数
    | 属性取用函数
    | 标记函数
    | 取消标记函数
    | 进入管线函数
    | 有标记函数
    | 调用结算函数
    | 状态函数
    | 结算目标标记函数
    | 护盾函数
    | 异常函数
    | 驱散函数
)


class 流程语法错误(ValueError):
    """判定公式不符合中文标准 DSL 约定。"""


def 从属性总表加载用途名(wb_or_path) -> set[str]:
    """从工作簿「属性总表」读取用途名集合（表头行含「属性用途名」，取列 B）。"""
    from openpyxl import load_workbook

    own = False
    if isinstance(wb_or_path, (str, Path)):
        wb = load_workbook(wb_or_path, data_only=True, read_only=True)
        own = True
    else:
        wb = wb_or_path
    try:
        ws = wb["属性总表"]
        header_row = None
        for r in range(1, min(30, (ws.max_row or 1) + 1)):
            if ws.cell(r, 2).value == "属性用途名":
                header_row = r
                break
        if header_row is None:
            raise 流程语法错误("属性总表未找到表头「属性用途名」（列 B）")
        names: set[str] = set()
        for r in range(header_row + 1, (ws.max_row or header_row) + 1):
            v = ws.cell(r, 2).value
            if v is None or v == "":
                continue
            names.add(str(v).strip())
        return names
    finally:
        if own:
            wb.close()


def _match_call_arg(s: str, start: int) -> tuple[str, int]:
    """从 ``func(`` 的左括号位置起，取平衡括号内参数；返回 (arg, end_exclusive)。"""
    if start >= len(s) or s[start] != "(":
        raise 流程语法错误(f"期望 '(' 于位置 {start}: {s[:80]}")
    depth = 0
    i = start
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
        i += 1
    raise 流程语法错误(f"括号不配对：{s[:80]}")


def _iter_func_calls(s: str, func_name: str) -> Iterable[tuple[str, int, int]]:
    """产出 (arg, start_of_name, end_after_closing_paren)。"""
    i = 0
    n = len(func_name)
    while True:
        j = s.find(func_name, i)
        if j < 0:
            return
        # 确保是完整标识（左侧不是标识续字符）
        if j > 0 and _IDENT_RE.match(s[j - 1 : j]):
            i = j + n
            continue
        k = j + n
        if k >= len(s) or s[k] != "(":
            i = j + n
            continue
        arg, end = _match_call_arg(s, k)
        yield arg, j, end
        i = end


def _split_top_args(arg: str) -> list[str]:
    """按顶层逗号切分参数（忽略括号内逗号）。"""
    parts: list[str] = []
    depth = 0
    last = 0
    for i, ch in enumerate(arg):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(arg[last:i].strip())
            last = i + 1
    parts.append(arg[last:].strip())
    return parts


def _strip_calls(s: str, func_names: Iterable[str]) -> str:
    """将指定函数调用替换为空格，便于扫描剩余标识。"""
    out = s
    for fn in func_names:
        pieces: list[str] = []
        last = 0
        for arg, start, end in list(_iter_func_calls(out, fn)):
            pieces.append(out[last:start])
            pieces.append(" ")
            last = end
        pieces.append(out[last:])
        out = "".join(pieces)
    return out


def 校验判定公式(expr: str, 属性名集合: set[str] | frozenset[str] | None = None) -> None:
    """校验一条中文 DSL 判定公式。

    Parameters
    ----------
    expr:
        判定公式字符串。
    属性名集合:
        「属性总表」用途名。若提供，则校验 ``效果/攻方/守方/结算目标属性`` 参数；
        若为 None，仅做句法与英文残留检查（不校验属性存在性）。

    Raises
    ------
    流程语法错误
    """
    if expr is None or not str(expr).strip():
        raise 流程语法错误("判定公式为空")
    s = str(expr).strip()
    # 统一去掉可选空格（校验用）
    compact = re.sub(r"\s+", "", s)

    for ban in _BANNED_ENGLISH:
        if ban in compact or ban in s:
            raise 流程语法错误(f"残留英文 Aviator「{ban}」：{s[:80]}")

    if compact.count("(") != compact.count(")"):
        raise 流程语法错误(f"括号不配对：{s[:80]}")

    # 属性取用：效果(用途名) | 效果(用途名,攻方|守方)；攻方/守方/结算目标属性 单参
    for arg, _a, _b in _iter_func_calls(compact, "效果"):
        parts = _split_top_args(arg)
        if len(parts) not in (1, 2) or not parts[0]:
            raise 流程语法错误(
                f"效果() 须一或两参数 (用途名[,攻方|守方])：{s[:80]}"
            )
        name = parts[0]
        if 属性名集合 is not None and name not in 属性名集合:
            raise 流程语法错误(
                f"效果({name}) 用途名不在属性总表：{s[:80]}"
            )
        if len(parts) == 2:
            role = parts[1]
            if role not in 角色枚举:
                raise 流程语法错误(
                    f"效果() 第二参数须为 {sorted(角色枚举)}：{s[:80]}"
                )
    for fn in ("攻方", "守方", "结算目标属性"):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            name = arg.strip()
            if not name:
                raise 流程语法错误(f"{fn}() 参数为空：{s[:80]}")
            if 属性名集合 is not None and name not in 属性名集合:
                raise 流程语法错误(
                    f"{fn}({name}) 用途名不在属性总表：{s[:80]}"
                )

    # 设结算目标(攻方|守方)
    for arg, _a, _b in _iter_func_calls(compact, "设结算目标"):
        role = arg.strip()
        if role not in 角色枚举:
            raise 流程语法错误(
                f"设结算目标() 参数须为 {sorted(角色枚举)}：{s[:80]}"
            )

    # 标记 / 取消标记
    for fn in ("标记", "取消标记"):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            flag = arg.strip()
            if flag not in 标记枚举:
                raise 流程语法错误(
                    f"{fn}({flag}) 非法，须为 {sorted(标记枚举)}：{s[:80]}"
                )

    # 有标记 / 结算目标有标记
    for fn in ("有标记", "结算目标有标记"):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            flag = arg.strip()
            if flag not in 标记枚举:
                raise 流程语法错误(
                    f"{fn}({flag}) 非法，须为 {sorted(标记枚举)}：{s[:80]}"
                )

    # 调用结算 — 总分总后一律拒绝
    for arg, _a, _b in _iter_func_calls(compact, "调用结算"):
        raise 流程语法错误(
            f"调用结算 已禁用（扣血/回血内联总分总，勿调用已删子管线）：{s[:80]}"
        )

    # 有状态 / 结算目标有状态
    for fn in ("有状态", "结算目标有状态"):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            tok = arg.strip()
            if tok not in 状态枚举:
                raise 流程语法错误(
                    f"{fn}({tok}) 非法，须为 {sorted(状态枚举)}：{s[:80]}"
                )

    # 护盾吸收(amount, 伤害类型|物理|魔法) — 兼容旧式
    for arg, _a, _b in _iter_func_calls(compact, "护盾吸收"):
        parts = _split_top_args(arg)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise 流程语法错误(
                f"护盾吸收() 须两参数 (量,伤害类型)：{s[:80]}"
            )
        kind = parts[1]
        if kind != "伤害类型" and kind not in 伤害类型字面量:
            raise 流程语法错误(
                f"护盾吸收 第二参数须为 伤害类型 或 {sorted(伤害类型字面量)}：{s[:80]}"
            )

    # 护盾类型可吸收(当前护盾,伤害类型|…)
    for arg, _a, _b in _iter_func_calls(compact, "护盾类型可吸收"):
        parts = _split_top_args(arg)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise 流程语法错误(
                f"护盾类型可吸收() 须两参数 (护盾,伤害类型)：{s[:80]}"
            )
        kind = parts[1]
        if kind != "伤害类型" and kind not in 伤害类型字面量:
            raise 流程语法错误(
                f"护盾类型可吸收 第二参数须为 伤害类型 或 {sorted(伤害类型字面量)}：{s[:80]}"
            )

    # 取护盾层 / 护盾剩余容量：单参
    for fn in ("取护盾层", "护盾剩余容量"):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            if not arg.strip():
                raise 流程语法错误(f"{fn}() 参数为空：{s[:80]}")

    # 扣减护盾层(当前护盾,本层吸收)
    for arg, _a, _b in _iter_func_calls(compact, "扣减护盾层"):
        parts = _split_top_args(arg)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise 流程语法错误(
                f"扣减护盾层() 须两参数 (护盾,吸收量)：{s[:80]}"
            )

    # 效果事件管线助手（挂载/叠层等；局部标识仍为异常*）
    for fn in (
        "效果标签被免疫",
        "互斥组冲突",
        "移除互斥组效果",
        "移除同效果",
        "有同效果",
        "结算目标递减系数",
    ):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            if not arg.strip():
                raise 流程语法错误(f"{fn}() 参数为空：{s[:80]}")
    for arg, _a, _b in _iter_func_calls(compact, "挂载效果"):
        parts = _split_top_args(arg)
        if len(parts) != 3 or not all(parts):
            raise 流程语法错误(
                f"挂载效果() 须三参数 (效果代号,层数,剩余时长)：{s[:80]}"
            )

    # 快照
    for arg, _a, _b in _iter_func_calls(compact, "写入快照"):
        if not arg.strip():
            raise 流程语法错误(f"写入快照() 参数为空：{s[:80]}")

    # 驱散助手
    for fn in ("选取可驱散效果", "移除效果", "执行到期动作"):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            if not arg.strip():
                raise 流程语法错误(f"{fn}() 参数为空：{s[:80]}")
    for arg, _a, _b in _iter_func_calls(compact, "匹配驱散类型"):
        parts = _split_top_args(arg)
        if len(parts) != 2 or not all(parts):
            raise 流程语法错误(
                f"匹配驱散类型() 须两参数 (标签,驱散类型)：{s[:80]}"
            )
    for arg, _a, _b in _iter_func_calls(compact, "转移效果"):
        parts = _split_top_args(arg)
        if len(parts) != 2 or not all(parts):
            raise 流程语法错误(
                f"转移效果() 须两参数 (效果代号,攻方|守方)：{s[:80]}"
            )
        if parts[1] not in 角色枚举:
            raise 流程语法错误(
                f"转移效果() 第二参数须为 {sorted(角色枚举)}：{s[:80]}"
            )

    for arg, _a, _b in _iter_func_calls(compact, "进入管线"):
        name = arg.strip()
        if not name:
            raise 流程语法错误(f"进入管线() 缺少管线名：{s[:80]}")
        if name not in 规划管线名:
            raise 流程语法错误(
                f"进入管线「{name}」不在规划管线名 {sorted(规划管线名)}：{s[:80]}"
            )

    # 设值 / 数值函数：至少有参数即可（内容再递归由剩余标识扫描覆盖）
    for fn in (
        list(设值函数)
        + list(二元数值函数)
        + list(三元数值函数)
        + list(无参函数)
        + list(状态函数)
        + list(结算目标标记函数)
        + list(护盾函数)
        + list(有标记函数)
        + list(取消标记函数)
        + list(进入管线函数)
        + list(异常函数)
        + list(驱散函数)
    ):
        for arg, _a, _b in _iter_func_calls(compact, fn):
            if fn in 无参函数 and arg.strip():
                raise 流程语法错误(f"{fn}() 不应有参数：{s[:80]}")
            if fn == "设结算目标":
                continue  # 已单独校验
            if fn not in 无参函数 and not arg.strip():
                raise 流程语法错误(f"{fn}() 参数为空：{s[:80]}")

    # 剥离已知函数调用后，扫描剩余标识符
    stripped = compact
    all_funcs = (
        list(属性取用函数)
        + list(标记函数)
        + list(取消标记函数)
        + list(进入管线函数)
        + list(有标记函数)
        + list(调用结算函数)
        + list(设值函数)
        + list(二元数值函数)
        + list(三元数值函数)
        + list(无参函数)
        + list(状态函数)
        + list(结算目标标记函数)
        + list(护盾函数)
        + list(异常函数)
        + list(驱散函数)
    )
    stripped = _strip_calls(stripped, all_funcs)
    # 去掉数字字面量
    stripped = re.sub(r"\d+(\.\d+)?", " ", stripped)
    # 去掉运算符与括号逗号
    stripped = re.sub(r"[+\-*/()<>=!|&,]", " ", stripped)

    allowed_idents = (
        管线局部标识符
        | 布尔字面量
        | 伤害类型字面量
        | 标记枚举
        | 状态枚举
        | 角色枚举
        | 效果类型字面量
        | 叠加规则字面量
        | 刷新规则字面量
        | 命中位字面量
        | 暴击位字面量
        | 伤害来源字面量
        | 治疗来源字面量
        | 生效时机字面量
        | 数值类型字面量
        | 空字面量
        | 模式字面量
        | 规划管线名
        | 是否字面量
        | 快照时机字面量
        | 驱散类型等级字面量
        | 驱散通道字面量
        | frozenset(all_funcs)
    )
    for m in _IDENT_RE.finditer(stripped):
        name = m.group(0)
        if name in allowed_idents:
            continue
        # 纯英文残留
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise 流程语法错误(f"未允许的英文标识「{name}」于：{s[:80]}")
        raise 流程语法错误(f"未允许的标识符「{name}」于：{s[:80]}")


def 校验步骤名(name: str) -> None:
    """步骤名须在规范化白名单内。"""
    if name not in 规范化步骤名:
        raise 流程语法错误(f"步骤名「{name}」不在规范化白名单")
