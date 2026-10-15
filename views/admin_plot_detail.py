"""农技员端 · 地块详情页。

包含：基础信息 / 生长档案时间轴 / 病害趋势 / 农事日志 / 长期管理建议 / 生产计划。
"""
from __future__ import annotations

import html
from collections import Counter

import streamlit as st

from config import GROWTH_STAGES, SOIL_TYPES
from components.charts import hbar_html
from components.layout import fmt_cn_time, info_grid_html, render_plan_block
from memory import history as memory
from memory import profiles
from services import stats
from services import crop_plan
from services.ai_service import generate_management_advice

# 注意：原先这里还有 _RISK_VALUE 与 risk_trend_rows（用于折线图）。
# 折线图已改为风险等级分布横向条形图（日期刻度竖排难读、且与其它图表不统一），
# 这两项随之删除，避免留下无调用的死代码。
_LOG_META = {
    "灌溉": ("灌溉", "灌溉"),
    "施肥": ("施肥", "施肥"),
    "打药": ("打药", "打药"),
    "巡田": ("巡田", "巡田"),
}


# ---------------------------------------------------------------------------
# 纯函数（供页面渲染与测试复用）
# ---------------------------------------------------------------------------
def build_timeline(records: list, profile: dict, logs: list) -> list[tuple]:
    """组装生长档案时间轴事件：(时间, 标题, 详情)，按时间正序。"""
    events: list[tuple] = []

    if profile.get("planting_date"):
        events.append((profile["planting_date"], "播种", "计划播种时间"))

    prev_stage = None
    for r in sorted(records, key=lambda x: x.get("timestamp", "")):
        stage = r.get("growth_stage", "")
        if stage and stage != prev_stage:
            events.append((r["timestamp"], f"生育阶段　{stage}", "阶段变化记录"))
            prev_stage = stage
        risk = r.get("risk_level") or "未知"
        events.append((
            r["timestamp"], "智能诊断",
            f"{r.get('growth_stage','')}　风险 {risk}　{r.get('diagnosis_summary','')[:50]}",
        ))
        rec_text = r.get("recommendation_summary", "")
        if any(k in rec_text for k in ("防治", "打药", "喷雾", "药剂")):
            events.append((r["timestamp"], "防治记录", rec_text[:80]))

    for lg in logs:
        label = _LOG_META.get(lg.get("type", ""), (lg.get("type", ""),))[0]
        events.append((lg["timestamp"], label, lg.get("note", "")))

    events.sort(key=lambda e: e[0])
    return events


def disease_counter_rows(records: list) -> list[dict]:
    """该地块病害出现次数（基于诊断文本识别）。"""
    counter: Counter = Counter()
    for r in records:
        text = f"{r.get('diagnosis_summary','')} {r.get('recommendation_summary','')}"
        counter[stats.match_disease(text)] += 1
    return [{"病害": d, "次数": c} for d, c in counter.most_common()]


# ---------------------------------------------------------------------------
# 页面渲染
# ---------------------------------------------------------------------------
def render(plot_key: str) -> None:
    if st.button("返回地块列表"):
        st.session_state["admin_plot_detail"] = None
        st.rerun()

    summary = next(
        (p for p in memory.list_plots() if p["plot_key"] == plot_key), None
    )
    if summary is None:
        st.warning("未找到该地块档案（可能已被删除）。")
        return

    location, crop, area = summary["location"], summary["crop"], summary["area"]
    records = memory.get_history(location, crop, area, limit=200)
    profile = profiles.get_profile(plot_key)
    logs = profiles.get_logs(plot_key)

    st.subheader(f"地块详情　{location or '未命名地块'}（{crop}）")

    # ------------------------------------------------------------------
    # 1. 基础信息
    # ------------------------------------------------------------------
    st.markdown("### 基础信息")
    st.markdown(
        info_grid_html([
            ("地块名称", location or "未命名地块"),
            ("种植面积", f"{area} 亩"),
            ("作物", crop),
        ]),
        unsafe_allow_html=True,
    )

    with st.form("profile_form"):
        c1, c2, c3, c4 = st.columns(4)
        current_soil = profile.get("soil_type", "")
        soil_index = SOIL_TYPES.index(current_soil) + 1 if current_soil in SOIL_TYPES else 0
        soil = c1.selectbox("土壤类型", ["未填写"] + SOIL_TYPES, index=soil_index)
        lat = c2.text_input("纬度", value=profile.get("latitude", ""), placeholder="如 39.90")
        lng = c3.text_input("经度", value=profile.get("longitude", ""), placeholder="如 116.40")
        planting = c4.text_input("播种时间", value=profile.get("planting_date", ""), placeholder="如 2026-04-20")
        if st.form_submit_button("保存基础信息"):
            profiles.save_profile(
                plot_key, soil_type=soil, latitude=lat.strip(),
                longitude=lng.strip(), planting_date=planting.strip(),
            )
            st.success("已保存基础信息")
            st.rerun()

    # ------------------------------------------------------------------
    # 2. 生长档案时间轴
    # ------------------------------------------------------------------
    st.markdown("### 生长档案")
    events = build_timeline(records, profile, logs)
    if not events:
        st.caption("暂无档案事件　可在下方补充农事日志，或由农户端诊断自动建档。")
    else:
        # 注意（重要教训）：这段 HTML 必须**顶格无缩进**。
        # 之前用带缩进的三引号字符串开头，Markdown 把缩进 ≥4 空格的行当成
        # 代码块，结果整段 `<div class="tl">…` 被原样显示成乱码。
        # 样式也已上移到 theme.py 的 `.ag-tl*` 类，这里只输出结构。
        parts = ['<div class="ag-tl">']
        for ts, title, detail in events:
            time_txt = fmt_cn_time(ts) if len(ts) > 10 else ts
            detail_html = (
                f'<div class="ag-tl-detail">{html.escape(str(detail))}</div>'
                if detail else ""
            )
            parts.append(
                f'<div class="ag-tl-item"><span class="ag-tl-dot"></span>'
                f'<div class="ag-tl-time">{html.escape(str(time_txt))}</div>'
                f'<div class="ag-tl-title">{html.escape(str(title))}</div>'
                f'{detail_html}</div>'
            )
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 3. 病害趋势
    # ------------------------------------------------------------------
    st.markdown("### 病害趋势")
    if records:
        st.markdown("风险等级分布")
        # 用横向条形图替代折线图：
        # 原先 st.line_chart 把日期当成 x 轴刻度，长日期被旋转成竖排、难以阅读，
        # 且与页面其它图表风格不一致。风险等级本质是离散分类（高/中/低/无），
        # 用横向条形图 + 风险配色更直观，也与"病害出现次数"两图格式统一。
        risk_counter = Counter(
            (r.get("risk_level") or "未知") for r in records
        )
        risk_order = ["高", "中", "低", "无", "未知"]
        risk_rows = [
            (f"{lv}风险" if lv != "未知" else "未知", risk_counter[lv])
            for lv in risk_order if risk_counter.get(lv)
        ]
        risk_colors = {
            "高风险": "#c0392b", "中风险": "#e67e22",
            "低风险": "#1976d2", "无风险": "#2e7d32", "未知": "#b0bec5",
        }
        st.markdown(
            hbar_html(risk_rows, unit="次", colors=risk_colors, show_pct=True),
            unsafe_allow_html=True,
        )

        st.markdown("病害出现次数")
        # 横向条形图：与数据总览/病害统计保持一致，
        # 避免 st.bar_chart 把长中文病害名旋转成竖排。
        st.markdown(
            hbar_html([(d["病害"], d["次数"]) for d in disease_counter_rows(records)],
                      unit="次", show_pct=True),
            unsafe_allow_html=True,
        )
    else:
        st.caption("暂无诊断记录，无法生成趋势图。")

    # ------------------------------------------------------------------
    # 4. 农事日志
    # ------------------------------------------------------------------
    st.markdown("### 农事日志")
    with st.form("log_form"):
        c1, c2, c3 = st.columns([1, 2, 1])
        log_type = c1.selectbox("日志类型", list(_LOG_META))
        note = c2.text_input(
            "内容",
            placeholder="如 滴灌 2 小时　追施尿素 5kg/亩　吡虫啉 1500 倍液　发现叶斑加重",
        )
        submitted = c3.form_submit_button("添加日志")
        if submitted:
            if note.strip():
                profiles.add_log(plot_key, log_type, note)
                st.success("已添加农事日志")
                st.rerun()
            else:
                st.warning("请填写日志内容")

    if logs:
        for lg in reversed(logs):
            st.markdown(f"{fmt_cn_time(lg['timestamp'])}　{lg.get('type', '')}　{lg.get('note', '')}")
    else:
        st.caption("暂无农事日志。")

    # ------------------------------------------------------------------
    # 5. 地块长期管理建议
    # ------------------------------------------------------------------
    st.markdown("### 地块长期管理建议")
    if st.button("生成地块长期管理建议", type="primary"):
        with st.spinner("正在综合分析地块档案…"):
            advice = generate_management_advice(plot_key, records, profile, logs)
        st.session_state["plot_advice"] = {"plot_key": plot_key, "advice": advice}

    cached_advice = st.session_state.get("plot_advice")
    if cached_advice and cached_advice.get("plot_key") == plot_key:
        advice = cached_advice["advice"]
        if advice.get("success"):
            render_plan_block(
                advice["content"],
                title=f"{location or '未命名地块'} 地块长期管理建议（{crop}）",
                file_base=f"农智链AgriAgent_长期管理建议_{location or '未命名地块'}_{crop}",
                key_prefix="advice",
            )
        else:
            st.error(advice.get("content", "生成失败"))

    # ------------------------------------------------------------------
    # 6. 生产计划
    # ------------------------------------------------------------------
    st.markdown("### 生产计划")
    records_sorted = sorted(records, key=lambda r: r.get("timestamp", ""))
    latest_stage = records_sorted[-1].get("growth_stage", "生长期") if records_sorted else "生长期"
    stage_index = GROWTH_STAGES.index(latest_stage) if latest_stage in GROWTH_STAGES else 3
    plan_stage = st.selectbox(
        "计划起始生育阶段", GROWTH_STAGES, index=stage_index, key="plot_plan_stage"
    )
    if st.button("生成未来 30 天生产计划", key="plot_plan_btn"):
        with st.spinner("正在制定 30 天农事计划…"):
            plan = crop_plan.generate_plan(
                crop=crop, growth_stage=plan_stage, area=area,
                records=records, logs=logs,
                soil_type=profile.get("soil_type", ""),
            )
        st.session_state["plot_plan"] = {"plot_key": plot_key, "plan": plan}

    cached_plan = st.session_state.get("plot_plan")
    if cached_plan and cached_plan.get("plot_key") == plot_key:
        plan = cached_plan["plan"]
        if plan.get("success"):
            render_plan_block(
                plan["content"],
                title=f"{crop} 地块未来 30 天农事计划（{area} 亩）",
                file_base=f"农智链AgriAgent_生产计划_{location or '未命名地块'}_{crop}",
                key_prefix="plotplan",
            )
        else:
            st.error(plan.get("content", "生成失败"))
