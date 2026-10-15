"""统计服务：基于 memory 历史诊断数据，为农技员管理端提供统计分析。"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from knowledge_center.loader import load_diseases
from memory import history as memory
from timeutil import now_cn, today_cn

# 知识库条目（用于从诊断文本中识别病害名称）
# 数据源与 Agent / RAG 统一：knowledge_center（P2-2，替换旧 knowledge.base）
_KB = load_diseases()


def _strip_crop_prefix(disease: str, crop: str) -> str:
    """去掉病名中的作物前缀（如 玉米丝黑穗病 → 丝黑穗病），用于核心词匹配。"""
    if crop and disease.startswith(crop) and len(disease) > len(crop):
        return disease[len(crop):]
    return disease


def match_disease(text: str) -> str:
    """从诊断文本中识别病害名称：完整病名 → 别名 → 核心词 → 兜底。

    匹配规则（P2-2，与 knowledge_center 统一数据源）：
    1. 标准病名包含：disease 是文本子串（原逻辑）；
    2. 别名包含：alias(len>=3) 是文本子串（原逻辑）；
    3. 核心词双向包含：文本包含"去掉作物前缀的病名核心词"(len>=3)，
       多个候选时优先返回文本中明确提及作物的条目（作物约束消歧）；
    4. 作物约束短词：文本明确提及作物名时，允许该作物条目以 >=2 字
       核心词命中（如 "小麦 蚜虫" → 小麦蚜虫）；
    5. 通用兜底（原逻辑）：真菌/虫害/缺素 → 泛化类别。
    """
    if not text:
        return "未识别"
    # 1. 标准病名包含（全库，原逻辑）
    for entry in _KB:
        if entry.get("disease") and entry["disease"] in text:
            return entry["disease"]

    # 文本中明确提及的作物名（作物约束：避免跨作物别名误匹配）
    mentioned_crops = {
        str(e.get("crop") or "") for e in _KB if e.get("crop") and e["crop"] in text
    }

    # 2a. 别名匹配 · 作物约束优先：文本提及作物时优先在该作物条目中匹配，
    #     别名去掉作物前缀后允许 >=3 字（如 花生褐斑病→褐斑病）；
    #     2 字别名由第 4 轮作物约束兜住，避免"疫病"类短词子串误匹配
    if mentioned_crops:
        for entry in _KB:
            if str(entry.get("crop") or "") in mentioned_crops:
                for alias in entry.get("aliases", []):
                    if not alias:
                        continue
                    if len(alias) >= 3 and alias in text:
                        return entry["disease"]
                    core_alias = _strip_crop_prefix(str(alias), str(entry.get("crop") or ""))
                    if len(core_alias) >= 3 and core_alias in text:
                        return entry["disease"]

    # 2b. 别名匹配 · 全库（原逻辑，len>=3 先到先得）
    for entry in _KB:
        for alias in entry.get("aliases", []):
            if alias and len(alias) >= 3 and alias in text:
                return entry["disease"]

    # 3. 核心词双向包含（disease 核心词命中文本）
    candidates: list[str] = []
    for entry in _KB:
        disease = str(entry.get("disease") or "")
        core = _strip_crop_prefix(disease, str(entry.get("crop") or ""))
        if len(core) >= 3 and core in text:
            candidates.append(disease)
    if candidates:
        # 作物约束消歧：文本明确提及作物时优先返回该作物的条目
        for entry in _KB:
            if entry.get("disease") in candidates and str(entry.get("crop") or "") in text:
                return entry["disease"]
        return candidates[0]

    # 4. 作物约束（文本含作物名时允许 >=2 字核心词/别名）
    for entry in _KB:
        crop = str(entry.get("crop") or "")
        disease = str(entry.get("disease") or "")
        if crop and crop in text:
            core = _strip_crop_prefix(disease, crop)
            if len(core) >= 2 and core in text:
                return disease
            for alias in entry.get("aliases", []):
                if alias and len(alias) >= 2 and alias in text:
                    return disease

    if "真菌" in text:
        return "真菌性病害"
    if "蚜虫" in text or "虫害" in text:
        return "虫害类"
    if "缺素" in text or ("缺" in text and "肥" in text):
        return "缺素/生理性"
    return "未识别"


def _record_text(record: dict) -> str:
    return f"{record.get('diagnosis_summary', '')} {record.get('recommendation_summary', '')}"


def _parse_ts(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return now_cn()


def overview() -> dict:
    """数据总览指标。

    注意区分两个容易混淆的口径：
      - `farmers`：**农户档案数**（farmers 表），代表真正建档的农户量；
      - `locations`：诊断记录里出现的**不重复地块位置数**。
    早期版本把 `locations` 当作"覆盖农户数量"显示，会高估农户数
    （实测：位置去重 6，而 farmers 表只有 4 条）。界面应使用 `farmers`。
    """
    records = memory.get_all_records()
    plots = memory.list_plots()
    total = len(records)
    crops = sorted({r.get("crop", "") or "未知" for r in records})
    risks = Counter((r.get("risk_level") or "未知") for r in records)
    high = risks.get("高", 0)

    locations = len({(r.get("location") or "").strip() or "未登记地块" for r in records})
    farmers = 0
    try:
        from database import repository as repo
        farmers = repo.count_farmers()
    except Exception:
        farmers = 0

    now = now_cn()
    last7 = sum(1 for r in records if (now - _parse_ts(r.get("timestamp", ""))).days < 7)
    last_time = max((r.get("timestamp", "") for r in records), default="")
    return {
        "plots": len(plots),
        "total_visits": total,
        "crops": len(crops),
        "crop_names": crops,
        "farmers": farmers,
        "locations": locations,
        "last7": last7,
        "high_risk": high,
        "high_ratio": round(high / total * 100, 1) if total else 0.0,
        "last_time": last_time,
    }


def crop_distribution() -> list[dict]:
    """作物分布：诊断次数 + 地块数。"""
    records = memory.get_all_records()
    visit_count = Counter((r.get("crop", "") or "未知") for r in records)
    plot_count = Counter((p.get("crop", "") or "未知") for p in memory.list_plots())
    crops = sorted(set(visit_count) | set(plot_count))
    return [
        {"作物": c, "诊断次数": visit_count.get(c, 0), "地块数": plot_count.get(c, 0)}
        for c in crops
    ]


def disease_distribution() -> list[dict]:
    """病害统计：按识别病害名聚合。"""
    counter: Counter = Counter()
    for r in memory.get_all_records():
        counter[match_disease(_record_text(r))] += 1
    return [{"病害": d, "次数": c} for d, c in counter.most_common()]


def risk_distribution() -> list[dict]:
    """风险等级统计（固定顺序：高/中/低/无/未知 · 含次数与占比）。"""
    order = ["高", "中", "低", "无", "未知"]
    records = memory.get_all_records()
    total = len(records)
    counter = Counter((r.get("risk_level") or "未知") for r in records)
    return [
        {
            "风险等级": lv,
            "次数": counter.get(lv, 0),
            "占比": f"{round(counter.get(lv, 0) / total * 100, 1) if total else 0}%",
        }
        for lv in order
    ]


def daily_trend(days: int = 30) -> list[dict]:
    """近 N 天每日诊断次数（缺失日期补 0）。"""
    counter: Counter = Counter()
    for r in memory.get_all_records():
        ts = r.get("timestamp", "")
        if ts:
            counter[ts[:10]] += 1
    today = today_cn()
    return [
        {
            "日期": (today - timedelta(days=i)).isoformat(),
            "诊断次数": counter.get((today - timedelta(days=i)).isoformat(), 0),
        }
        for i in range(days - 1, -1, -1)
    ]


def high_risk_records() -> list[dict]:
    """高风险记录清单。"""
    return [r for r in memory.get_all_records() if (r.get("risk_level") or "未知") == "高"]


def plot_summaries() -> list[dict]:
    """地块档案汇总（附带识别病害）。"""
    plots = memory.list_plots()
    for p in plots:
        p["disease"] = match_disease(
            f"{p.get('last_summary', '')} {p.get('last_recommendation', '')}"
        )
    return plots


def risk_plot_table() -> list[dict]:
    """风险地块列表：地块位置 / 作物 / 最近诊断 / 风险等级（高风险优先）。"""
    from components.layout import fmt_cn_time

    order = {"高": 0, "中": 1, "低": 2, "无": 3, "未知": 4}
    rows = [
        {
            "地块位置": (p["location"] or "未命名地块"),
            "作物": p["crop"],
            "最近诊断": f"{fmt_cn_time(p['last_time'])}　{(p['last_summary'] or '')[:20]}",
            "风险等级": p["last_risk"],
        }
        for p in memory.list_plots()
    ]
    rows.sort(key=lambda r: r["最近诊断"], reverse=True)
    rows.sort(key=lambda r: order.get(r["风险等级"], 9))
    return rows


def recent_table(limit: int = 0) -> list[dict]:
    """历史记录表格（limit=0 表示全部）。"""
    from components.layout import fmt_cn_time

    out = []
    for r in memory.get_all_records(limit=limit or None):
        out.append({
            "时间": fmt_cn_time(r.get("timestamp", "")),
            "地块位置": (r.get("location") or "未命名地块"),
            "作物": r.get("crop", ""),
            "生育阶段": r.get("growth_stage", ""),
            "风险等级": r.get("risk_level") or "未知",
            "识别病害": match_disease(_record_text(r)),
            "诊断摘要": (r.get("diagnosis_summary", "") or "")[:30],
        })
    return out


__all__ = [
    "match_disease",
    "overview",
    "crop_distribution",
    "disease_distribution",
    "risk_distribution",
    "daily_trend",
    "high_risk_records",
    "plot_summaries",
    "risk_plot_table",
    "recent_table",
]
