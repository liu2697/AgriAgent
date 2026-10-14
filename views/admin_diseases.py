"""农技员端 · 病害统计分析。"""
from __future__ import annotations

import html

import streamlit as st

from components.charts import hbar_html
from services import stats


def render() -> None:
    st.subheader("历史诊断病害统计")
    st.caption(
        "按已接入农户的诊断记录聚合，反映当前业务数据中的病害发生情况；"
        "不代表平台知识库的病害覆盖范围（知识库覆盖见「数据总览 → 农业知识能力」）。"
    )

    dist = stats.disease_distribution()
    if not dist:
        st.info("暂无数据。农户端完成诊断后可查看统计。")
        return

    total = sum(d["次数"] for d in dist)

    # ---- 概览 ----
    c1, c2, c3 = st.columns(3)
    c1.metric("诊断记录总数", f"{total} 条")
    c2.metric("识别到的病害种类", f"{len(dist)} 类")
    top = dist[0]
    c3.metric("发生最多", top["病害"], f"{top['次数']} 次")

    st.divider()

    # ---- 横向条形图（标签水平显示，避免长中文被竖排）----
    left, right = st.columns([1.35, 1])
    with left:
        st.markdown("**病害出现次数**（当前已接入数据）")
        st.markdown(
            hbar_html([(d["病害"], d["次数"]) for d in dist],
                      unit="", show_pct=True),
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("**病害明细**")
        rows = []
        for d in dist:
            pct = round(d["次数"] / total * 100, 1) if total else 0
            rows.append(
                f'<div class="ag-mini-stat">'
                f'<div class="ag-mini-stat-lbl">{html.escape(str(d["病害"]))}</div>'
                f'<div class="ag-mini-stat-val">{d["次数"]}<sub>次</sub></div>'
                f'<div class="ag-mini-stat-hint">占比 {pct}%</div>'
                f'</div>'
            )
        st.markdown(f'<div class="ag-mini-stats">{"".join(rows)}</div>',
                    unsafe_allow_html=True)

    st.divider()

    # ---- 作物分布 ----
    st.markdown("**作物诊断分布**（当前已接入数据）")
    crops = stats.crop_distribution()
    st.markdown(
        hbar_html([(c["作物"], c["诊断次数"]) for c in crops], unit="", show_pct=True),
        unsafe_allow_html=True,
    )
