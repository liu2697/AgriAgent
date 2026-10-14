"""农技员端 · 风险等级统计。"""
from __future__ import annotations

import html

import streamlit as st

from components.charts import RISK_COLORS, hbar_html
from components.layout import fmt_cn_time
from memory import history as memory
from services import stats


def render() -> None:
    st.subheader("风险等级统计")
    st.caption("安全审核模块在每次诊断时自动评定风险等级。")

    records = memory.get_all_records()
    if not records:
        st.info("暂无数据。农户端完成诊断后可查看统计。")
        return

    dist = stats.risk_distribution()
    total = sum(r["次数"] for r in dist) or 1

    # ---- 概览 ----
    high = next((r["次数"] for r in dist if r["风险等级"] == "高"), 0)
    mid = next((r["次数"] for r in dist if r["风险等级"] == "中"), 0)
    c1, c2, c3 = st.columns(3)
    c1.metric("诊断记录总数", f"{total} 条")
    c2.metric("高风险记录", f"{high} 条", f"占比 {high / total * 100:.1f}%")
    c3.metric("中风险记录", f"{mid} 条", f"占比 {mid / total * 100:.1f}%")

    st.divider()

    # ---- 横向条形图（标签水平显示）----
    left, right = st.columns([1.35, 1])
    with left:
        st.markdown("**各风险等级记录数**")
        st.markdown(
            hbar_html([(r["风险等级"], r["次数"]) for r in dist],
                      unit="", colors=RISK_COLORS, show_pct=True),
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("**分布明细**")
        rows = []
        for r in dist:
            level = r["风险等级"]
            color = RISK_COLORS.get(level, "#90a4ae")
            rows.append(
                f'<div class="ag-mini-stat" style="border-left-color:{color};">'
                f'<div class="ag-mini-stat-lbl">{html.escape(level)}风险</div>'
                f'<div class="ag-mini-stat-val" style="color:{color};">'
                f'{r["次数"]}<sub>条</sub></div>'
                f'<div class="ag-mini-stat-hint">占比 {r["占比"]}</div>'
                f'</div>'
            )
        st.markdown(f'<div class="ag-mini-stats">{"".join(rows)}</div>',
                    unsafe_allow_html=True)

    # ---- 高风险记录清单 ----
    high_risk = stats.high_risk_records()
    st.divider()
    if high_risk:
        st.markdown(f"**高风险记录**（共 {len(high_risk)} 条，需重点关注）")
        for r in high_risk:
            loc = r.get("location") or "未命名地块"
            with st.expander(f"{loc}　{fmt_cn_time(r['timestamp'])}"):
                st.markdown(f"- 作物　{r.get('crop', '')}")
                st.markdown(f"- 生育阶段　{r.get('growth_stage', '')}")
                st.markdown(f"- 诊断摘要　{r.get('diagnosis_summary', '')}")
                st.markdown(f"- 建议摘要　{r.get('recommendation_summary', '')[:200]}")
    else:
        st.success("目前没有高风险记录。")

    unknown = next((r["次数"] for r in dist if r["风险等级"] == "未知"), 0)
    if unknown:
        st.caption(
            f"有 {unknown} 条较早记录未保存风险等级，已标记为「未知」，新诊断将自动记录。"
        )
