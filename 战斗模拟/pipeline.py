"""批跑任务 → 编译双方 → 一场规则战斗 → 可选写回运行结果 / 战斗矩阵。"""
from __future__ import annotations

from datetime import datetime

from 战斗模拟.compile.entity import MissingLife, compile_monster, compile_player
from 战斗模拟.load.contract import load_contract
from 战斗模拟.load.snapshot import opening_panels
from 战斗模拟.sim.fight import run_fight
from 战斗模拟.sim.metrics import 汇总, 合并样本
from 战斗模拟.write.matrix import append_matrix_column
from 战斗模拟.write.results import append_results


def _enabled(tasks: list[dict], only: str | None) -> list[dict]:
    if only:
        return [t for t in tasks if str(t.get("任务名")) == only]
    return [t for t in tasks if str(t.get("启用") or "") == "是"]


def _scene(contract: dict, name: str) -> dict | None:
    for scene in contract["scenes"]:
        if str(scene.get("场景名")) == name:
            return scene
    return None


def _monster(contract: dict, name: str) -> dict | None:
    for row in contract["monsters"]:
        if str(row.get("怪物名")) == name:
            return row
    return None


def _build(contract: dict, name: str) -> dict | None:
    for row in contract["builds"]:
        if str(row.get("构筑名")) == name:
            return row
    return None


def _unit_row(contract: dict, name: str):
    build = _build(contract, name)
    if build:
        return "玩家", build
    monster = _monster(contract, name)
    if monster:
        return "怪物", monster
    return None, None


def _from_rule(contract: dict, rule: str) -> tuple[list, list] | None:
    if "全部构筑" in rule:
        return None
    allies, enemies = [], []
    for part in str(rule).split(";"):
        if "=" not in part:
            continue
        slot, name = part.split("=", 1)
        kind, row = _unit_row(contract, name.strip())
        if row is None:
            continue
        (allies if slot.strip().upper().startswith("A") else enemies).append((kind, row))
    if allies and enemies:
        return allies, enemies
    return None


def _from_scene(contract: dict, scene_name: str) -> tuple[list, list]:
    allies, enemies = [], []
    for slot in contract["slots"]:
        if str(slot.get("场景名")) != scene_name:
            continue
        name = str(slot.get("单位名") or "").strip()
        if not name:
            continue
        kind, row = _unit_row(contract, name)
        if row is None:
            continue
        side = str(slot.get("阵营") or "A")
        (allies if side == "A" else enemies).append((kind, row))
    return allies, enemies


def _matchups(contract: dict, task: dict) -> list[tuple[list, list]]:
    scene = _scene(contract, str(task.get("场景名") or ""))
    if scene is None:
        return []
    rule = str(task.get("对阵生成规则") or "")
    if "全部构筑" in rule:
        foes = _from_scene(contract, str(scene.get("场景名")))[1]
        if not foes:
            return []
        names = [str(b.get("构筑名")) for b in contract["builds"] if str(b.get("启用") or "是") != "否"]
        return [([("玩家", _build(contract, name))], foes) for name in names if _build(contract, name)]
    stated = _from_rule(contract, rule)
    if stated:
        return [stated]
    if rule and "全部构筑" not in rule:
        named = []
        for part in rule.split(";"):
            if "=" not in part:
                continue
            slot, name = part.split("=", 1)
            if not slot.strip().upper().startswith("A"):
                continue
            kind, row = _unit_row(contract, name.strip())
            if row:
                named.append((kind, row))
        foes = _from_scene(contract, str(scene.get("场景名")))[1]
        if named and foes:
            return [(named, foes)]
    allies, enemies = _from_scene(contract, str(scene.get("场景名")))
    if allies and enemies:
        return [(allies, enemies)]
    return []


def _spawn(kind: str, row: dict, side: str, contract: dict) -> dict:
    if kind == "玩家":
        unit = compile_player(
            row,
            contract["panels"].get(str(row.get("构筑名")), {}),
            contract["skills"],
            contract.get("profiles", {}).get(str(row.get("构筑名"))),
            contract.get("mastery"),
            contract.setdefault("待对齐", []),
        )
    else:
        unit = compile_monster(row, contract["skills"])
    unit["阵营"] = side
    return unit


def _granularity(task: dict) -> str:
    raw = str(task.get("输出粒度") or "").strip()
    if raw in ("矩阵", "长表", "全量"):
        return raw
    # 旧枚举兼容
    if raw in ("汇总", "分技能", "逐事件", ""):
        return "全量"
    return "全量"


def _column_title(task_name: str, match: str, run_id: str) -> str:
    short = (run_id or "")[-6:]
    match_short = match if len(match) <= 40 else match[:37] + "…"
    return f"{task_name}|{match_short}|{short}"


def run(workbook: str | None = None, task: str | None = None, write: bool = False) -> dict:
    contract = load_contract(workbook)
    contract["panels"] = opening_panels(contract["path"], contract["panels"])
    step_raw = contract["params"].get("事件时间精度")
    if step_raw in (None, ""):
        return {"ok": False, "原因": "模拟参数没有事件时间精度", "待对齐": contract.get("待对齐") or []}
    step = float(step_raw)
    fights = []
    skipped = []
    rows = []
    matrix_payloads = []
    run_id = datetime.now().strftime("R%Y%m%d%H%M%S")
    for item in _enabled(contract["tasks"], task):
        scene = _scene(contract, str(item.get("场景名") or ""))
        if scene is None or scene.get("时长上限") in (None, ""):
            skipped.append({"任务": item.get("任务名"), "对阵": "", "原因": "场景没有时长上限"})
            continue
        limit = float(scene["时长上限"])
        grain = _granularity(item)
        for allies, enemies in _matchups(contract, item):
            label = "、".join(row.get("构筑名") or row.get("怪物名") for _, row in allies)
            label += " vs " + "、".join(row.get("构筑名") or row.get("怪物名") for _, row in enemies)
            try:
                side_a = [_spawn(kind, row, "A", contract) for kind, row in allies]
                side_b = [_spawn(kind, row, "B", contract) for kind, row in enemies]
            except MissingLife as exc:
                skipped.append({"任务": item.get("任务名"), "对阵": label, "原因": str(exc)})
                continue
            samples = []
            repeats = item.get("次数") or 1
            try:
                repeats = max(1, int(float(repeats)))
            except (TypeError, ValueError):
                repeats = 1
            outcome = None
            for sample in range(repeats):
                seeded = dict(item)
                base_seed = item.get("种子")
                if base_seed not in (None, ""):
                    seeded["种子"] = int(float(base_seed)) + sample
                outcome = run_fight(contract, side_a, side_b, limit * 1000, step, scene, task=seeded)
                samples.extend(汇总(outcome, run_id, str(item.get("任务名")), str(item.get("场景名")), label, str(item.get("算法") or "掷骰")))
            merged = 合并样本(samples)
            if grain in ("长表", "全量"):
                rows.extend(merged)
            if grain in ("矩阵", "全量"):
                matrix_payloads.append((merged, _column_title(str(item.get("任务名")), label, run_id)))
            player = next(u for u in outcome["单位"] if u["阵营"] == "A")
            foes_down = all(u["生命值"] <= 0 for u in outcome["单位"] if u["阵营"] == "B")
            win = "胜" if foes_down else "未结束"
            fights.append({
                "任务": item.get("任务名"),
                "对阵": label,
                "时长秒": round(outcome["时长毫秒"] / 1000, 2),
                "伤害": round(player["伤害"], 1),
                "治疗": round(player["治疗"], 1),
                "胜负": win,
                "日志条数": len(outcome["日志"]),
                "指标条数": len(samples),
                "输出粒度": grain,
            })
    written = None
    matrix_written = None
    if write:
        if rows:
            written = append_results(contract["path"], rows)
        if matrix_payloads:
            import openpyxl
            wb = openpyxl.load_workbook(contract["path"])
            try:
                matrix_written = {}
                for payload, title in matrix_payloads:
                    cols = append_matrix_column(wb, payload, title)
                    for block, col in cols.items():
                        matrix_written.setdefault(block, []).append(col)
                wb.save(contract["path"])
            finally:
                wb.close()
    return {
        "ok": True,
        "path": contract["path"],
        "技能": len(contract["skills"]),
        "构筑": len(contract["builds"]),
        "任务": len(_enabled(contract["tasks"], task)),
        "战斗": fights,
        "跳过": skipped,
        "写回行": written,
        "矩阵列": matrix_written,
        "待对齐": contract.get("待对齐") or [],
    }
