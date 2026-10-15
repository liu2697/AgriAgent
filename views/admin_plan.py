"""农技员端 · 生产计划（30 天智能生产管理方案）。"""
import streamlit as st

from config import GROWTH_STAGES
from memory import history as memory
from memory import profiles
from services import crop_plan
from components import info_grid_html
from components.layout import render_plan_block


def render() -> None:
    # ========== 页头 ==========
    st.markdown(
        f"""
        <div class="ag-rpt-header">
            <span class="ag-rpt-hd-badge">生产计划</span>
            <div class="ag-rpt-hd-title">30天智能生产管理方案</div>
            <div class="ag-rpt-hd-sub">基于作物类型 生育阶段 历史诊断记录生成个性化农事建议</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    plots = memory.list_plots()
    if not plots:
        st.info("暂无地块档案。农户端完成诊断后系统会自动建档。")
        return

    # ========== 选择地块 ==========
    label_of = {p["plot_key"]: (p["location"] or "未命名地块") for p in plots}
    plot_key = st.selectbox(
        "选择地块",
        [p["plot_key"] for p in plots],
        format_func=lambda k: label_of.get(k, k),
        key="plan_plot_select",
    )
    p = next(x for x in plots if x["plot_key"] == plot_key)
    records = memory.get_history(p["location"], p["crop"], p["area"], limit=50)
    logs = profiles.get_logs(plot_key)
    profile = profiles.get_profile(plot_key)

    latest_stage = records[-1].get("growth_stage", "生长期") if records else "生长期"
    stage_index = GROWTH_STAGES.index(latest_stage) if latest_stage in GROWTH_STAGES else 3

    # ========== 地块信息卡片 ==========
    st.markdown(
        info_grid_html([
            ("地块名称", p["location"] or "未命名地块"),
            ("种植作物", p["crop"]),
            ("种植面积", f"{p['area']} 亩"),
            ("当前阶段", latest_stage),
            ("土壤类型", profile.get("soil_type") or "未填写"),
            ("历史诊断", f"{len(records)} 次"),
            ("最近风险等级", p["last_risk"]),
            ("农事日志", f"{len(logs)} 条"),
        ]),
        unsafe_allow_html=True,
    )

    plan_stage = st.selectbox(
        "方案起始生育阶段", GROWTH_STAGES, index=stage_index, key="plan_stage"
    )

    if st.button("生成30天智能农事管理方案", type="primary", key="gen_plan_btn"):
        with st.spinner("正在生成30天智能农事管理方案…"):
            plan = crop_plan.generate_plan(
                crop=p["crop"], growth_stage=plan_stage, area=p["area"],
                records=records, logs=logs, soil_type=profile.get("soil_type", ""),
            )
        st.session_state["admin_plan_result"] = {"plot_key": plot_key, "plan": plan}

    cached = st.session_state.get("admin_plan_result")
    if cached and cached.get("plot_key") == plot_key:
        plan = cached["plan"]
        if plan.get("success"):
            render_plan_block(
                plan["content"],
                title=f"{p['crop']} 地块 30 天农事管理方案（{p['area']} 亩）",
                file_base=f"农智链AgriAgent_30天生产管理方案_{p['crop']}_{p['area']}亩",
                key_prefix="adminplan",
            )
        else:
            st.error(plan.get("content", "生成失败"))
