"""农业生产计划服务：基于地块档案生成未来 30 天农事计划。

输入：作物 / 生育阶段 / 地块面积 / 历史诊断记录 / 最近农事日志
输出：按周拆分的 30 天农事计划（Markdown）

真实 AI 生成（配置 AI_API_KEY 时），否则使用内置规则模板兜底，
不依赖 Agent 核心流程（agent/ 包零改动）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from config import AI_API_KEY, AI_MODEL, GROWTH_STAGES
from services import stats
from services.ai_service import _request_ai
from timeutil import now_cn, today_cn

# 各生育阶段的基础农事任务（规则模板用）
_STAGE_TASKS = {
    "播种期": ["整地保墒，施足底肥", "播前种子处理（种衣剂拌种）", "播种后查苗补苗"],
    "发芽期": ["保持土壤墒情促出苗", "查苗补种", "防治苗期地下害虫"],
    "幼苗期": ["间苗定苗，中耕除草", "苗期追肥", "查治蚜虫与叶部病害"],
    "生长期": ["追施拔节/攻穗肥", "中耕培土防倒伏", "监测大斑病 锈病等叶部病害", "视墒情灌溉（每 7-10 天）"],
    "开花期": ["水肥临界期管理，保持供水", "授粉期避免高温干旱胁迫", "查治穗部害虫"],
    "结果期": ["按历史风险重点防治病虫害", "控制灌溉防止贪青", "做好收获前准备"],
    "成熟期": ["控水促成熟", "收获前 15 天停止用药", "收获 晾晒与入库安排"],
}


def _week_ranges() -> list[tuple[str, str]]:
    """未来 4 周的日期区间（MM-DD 格式）。"""
    today = today_cn()
    weeks = []
    for i in range(4):
        start = today + timedelta(days=i * 7)
        end = start + timedelta(days=6)
        weeks.append((start.strftime("%m-%d"), end.strftime("%m-%d")))
    return weeks


def _latest_disease(records: list) -> str:
    """从最近诊断记录中识别病害名称。"""
    if not records:
        return ""
    recs = sorted(records, key=lambda r: r.get("timestamp", ""))[-3:]
    text = " ".join(
        f"{r.get('diagnosis_summary', '')} {r.get('recommendation_summary', '')}"
        for r in recs
    )
    return stats.match_disease(text)


def _mock_plan(crop: str, growth_stage: str, area: float,
               records: list, logs: list, soil_type: str) -> str:
    """规则模板生成 30 天农事计划（无 AI Key 时兜底）。"""
    stage_idx = GROWTH_STAGES.index(growth_stage) if growth_stage in GROWTH_STAGES else 3
    next_stage = GROWTH_STAGES[stage_idx + 1] if stage_idx + 1 < len(GROWTH_STAGES) else None
    base_tasks = _STAGE_TASKS.get(growth_stage, _STAGE_TASKS["生长期"])
    next_tasks = _STAGE_TASKS.get(next_stage, []) if next_stage else []

    disease = _latest_disease(records)
    risk_last = "未知"
    if records:
        recs = sorted(records, key=lambda r: r.get("timestamp", ""))
        risk_last = recs[-1].get("risk_level") or "未知"

    recent_logs = logs[-4:] if logs else []
    fert_recent = any(lg.get("type") == "施肥" for lg in recent_logs)
    spray_recent = any(lg.get("type") == "打药" for lg in recent_logs)

    lines = [
        "⚠️ 当前未配置 AI 服务密钥，以下为规则模板生成的示例计划（仅演示）；"
        "配置密钥后，本方案将由大模型结合地块档案生成。",
        "",
        f"# {crop} · 未来 30 天农事计划",
        "",
        f"> 生成时间　{now_cn():%Y-%m-%d %H:%M}　生育阶段　{growth_stage}　"
        f"面积　{area} 亩　土壤　{soil_type or '未填写'}",
        "",
    ]

    for i, (start, end) in enumerate(_week_ranges()):
        lines.append(f"## 第{i + 1}周（{start} ~ {end}）")
        tasks = base_tasks if i < 2 else (next_tasks or base_tasks)
        for t in tasks[:3]:
            lines.append(f"- {t}")
        if i == 0 and not fert_recent:
            lines.append(f"- 追施氮肥　尿素 {round(area * 5, 1)} kg（{area} 亩 × 5 kg/亩），结合降雨或灌溉进行")
        if i == 1:
            lines.append("- 灌溉　视墒情每 7-10 天一次，避免大水漫灌，雨后及时排涝")
        if i == 2 and disease and disease != "未识别":
            lines.append(f"- 病害复查　重点巡查「{disease}」，发现病斑及时上报农技员")
        if i == 3:
            lines.append("- 巡田记录　记录生育进程与病虫发生情况，更新地块档案")
        lines.append("")

    lines.append("## 全周期监测要点")
    lines.append(f"- 最近诊断风险等级　{risk_last}")
    if disease and disease != "未识别":
        lines.append(f"- 历史识别病害　{disease}，未来 30 天需持续监测。")
    else:
        lines.append("- 暂无明确病害记录，按常规病虫监测执行。")
    if spray_recent:
        lines.append("- 近期已打药　再次用药请遵守安全间隔期（一般 7-10 天）。")
    if fert_recent:
        lines.append("- 近期已施肥　下次追肥间隔建议 ≥15 天，避免烧苗。")

    lines += ["", "---", "*本方案由系统生成，仅供辅助决策参考；实际农事请结合天气与当地农技人员指导。*", ""]
    return "\n".join(lines)


def generate_plan(crop: str, growth_stage: str, area: float,
                  records: list, logs: list, soil_type: str = "") -> dict:
    """生成未来 30 天农事计划，返回 {success, content, source}。"""
    if not AI_API_KEY:
        return {
            "success": True,
            "content": _mock_plan(crop, growth_stage, area, records, logs, soil_type),
            "source": "mock",
        }

    lines = [
        f"【地块信息】作物：{crop}，生育阶段：{growth_stage}，面积：{area} 亩，土壤：{soil_type or '未填写'}",
        f"【历史诊断 {len(records)} 次】",
    ]
    for r in records[-5:]:
        lines.append(
            f"- {r['timestamp'][:10]} | {r['growth_stage']} | 风险：{r.get('risk_level') or '未知'} | "
            f"诊断：{r['diagnosis_summary'][:50]} | 建议：{r['recommendation_summary'][:60]}"
        )
    if logs:
        lines.append(f"【最近农事记录 {len(logs)} 条】")
        for lg in logs[-5:]:
            lines.append(f"- {lg['timestamp'][:16]} | {lg['type']} | {lg['note'][:60]}")

    prompt = (
        "你是一位北方大田作物生产管理专家。请为以下地块制定「未来 30 天农事计划」，"
        "按周输出（第 1 周 ~ 第 4 周，给出大致日期区间），每周列出 3-5 项具体可执行的农事任务，"
        "并结合生育阶段、历史病害风险与最近农事记录（注意施肥/打药安全间隔期）。"
        "使用 Markdown 输出，总字数不超过 600 字。\n\n" + "\n".join(lines)
    )

    content, error = _request_ai(
        [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    )
    if content is None:
        return {"success": False, "content": f"AI 服务调用失败：{error}", "source": "error"}
    return {"success": True, "content": content, "source": AI_MODEL}


__all__ = ["generate_plan"]
