"""农技员端：农业问题工单系统 — 列表筛选 + 审核修改 + 发布跟踪。"""
from __future__ import annotations

import io

import streamlit as st
from PIL import Image

from config import APP_NAME, APP_SUBTITLE
from components.layout import fmt_cn_time, flow_steps_html, task_status_display
from memory import history as memory
from memory.history import (
    ALL_STATUSES,
    STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_CLOSED,
)


STATUS_COLOR = {
    STATUS_PENDING:    ("", "#b45309"),
    STATUS_PROCESSING: ("", "#1F6B45"),
    STATUS_COMPLETED:  ("", "#388e3c"),
    STATUS_CLOSED:     ("", "#9e9e9e"),
}

RISK_COLOR = {
    "高": "badge-high", "中": "badge-mid", "低": "badge-low", "无": "", "未知": "",
}


def _status_badge(status: str) -> str:
    _, color = STATUS_COLOR.get(status, ("", "#9e9e9e"))
    display = task_status_display(status)
    return (
        f'<span style="display:inline-block;padding:2px 10px;'
        f'border:1px solid {color}55;color:{color};font-size:12px;font-weight:600;">'
        f'{display}</span>'
    )


def _risk_badge(risk: str) -> str:
    cls = RISK_COLOR.get(risk, "")
    return f'<span class="badge {cls}">风险 {risk or "未知"}</span>'


def _short_id(task_id: str) -> str:
    """工单编号只显示短编号（隐藏内部完整 ID）。"""
    return f"TK-{task_id[-6:].upper()}"


def _render_md_preview(title: str, raw: str) -> None:
    """在 text_area 下方渲染格式预览块。"""
    if not raw or not raw.strip():
        return
    st.markdown(
        f"""
        <div style="margin:0.35rem 0 0.5rem;padding:0.55rem 0.75rem;
                    background:#f8fafc;border:1px dashed #cfd8dc;
                    border-radius:6px;">
            <div style="font-size:0.66rem;font-weight:700;color:#78909c;
                        letter-spacing:0.04em;margin-bottom:0.3rem;">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(raw)


def render() -> None:
    stats = memory.task_stats()

    # ========== 顶部 Header ==========
    st.markdown(
        f"""
        <div class="ag-rpt-header">
            <span class="ag-rpt-hd-badge">问题工单管理</span>
            <div class="ag-rpt-hd-title">{APP_NAME}</div>
            <div class="ag-rpt-hd-sub">{APP_SUBTITLE}</div>
            <div class="ag-rpt-hd-tags">
                <span class="ag-rpt-hd-tag">工单总数 {stats['total']}</span>
                <span class="ag-rpt-hd-tag">待审核 {stats['pending']}</span>
                <span class="ag-rpt-hd-tag">审核中 {stats['processing']}</span>
                <span class="ag-rpt-hd-tag">已发布 {stats['completed']}</span>
                <span class="ag-rpt-hd-tag">已完成 {stats['closed']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ========== 状态流转总览 ==========
    funnel = [
        (f"待审核 {stats['pending']}", "done" if stats["pending"] else "pending"),
        (f"审核中 {stats['processing']}", "done" if stats["processing"] else "pending"),
        (f"已发布 {stats['completed']}", "done" if stats["completed"] else "pending"),
        (f"已完成 {stats['closed']}", "done" if stats["closed"] else "pending"),
    ]
    st.markdown(flow_steps_html(funnel), unsafe_allow_html=True)

    # ========== 筛选区 ==========
    st.markdown("##### 筛选工单")

    f1, f2, f3, f4 = st.columns([1.2, 1, 1.5, 1])
    with f1:
        default_status = st.session_state.get("task_filter_status", "")
        status_filter = st.selectbox(
            "状态筛选",
            ["全部"] + list(ALL_STATUSES),
            index=([""] + list(ALL_STATUSES)).index(default_status) + 1
            if default_status in ALL_STATUSES else 0,
            format_func=lambda s: "全部" if s == "全部" else task_status_display(s),
            key="task_filter_status",
        )
        if status_filter == "全部":
            status_filter = ""
    with f2:
        crop_filter = st.text_input("作物", value="", placeholder="如 玉米")
    with f3:
        keyword = st.text_input("关键词", value="", placeholder="搜索地块 / 农户 / 症状")
    with f4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("清空全部", use_container_width=True):
            for tid in [t["task_id"] for t in memory.list_tasks()]:
                memory.delete_task(tid)
            st.success("已清空全部工单")
            st.rerun()

    tasks = memory.list_tasks(
        status=status_filter or "",
        crop=crop_filter.strip(),
        keyword=keyword.strip(),
    )

    st.markdown(f"##### 工单列表　共 {len(tasks)} 条")

    if not tasks:
        st.info("暂无工单。农户在诊断页面点击「提交农技员审核」后，工单会出现在这里。")
        return

    for task in tasks:
        _render_task_row(task)


def _render_task_row(task: dict) -> None:
    tid = task["task_id"]

    status_badge_html = _status_badge(task["status"])
    risk_badge_html = _risk_badge(task.get("ai_result", {}).get("risk_level", "未知"))
    crop = task["crop"]
    stage = task.get("growth_stage") or ""
    if stage in ("", "—"):
        stage = "未填写"
    area = task["area"]
    location = (task.get("location", "") or "").replace("·", " ")
    create = fmt_cn_time(task["create_time"])
    farmer = task.get("farmer_name", "")
    contact = task.get("contact", "")
    symptoms = task.get("symptoms", "")

    farmer_txt = f"　{farmer}" if farmer else ""
    contact_txt = f"　{contact}" if contact else ""
    loc_txt = f"　{location}" if location else ""

    st.markdown(
        f"**工单 {_short_id(tid)}**　{status_badge_html}　{risk_badge_html}",
        unsafe_allow_html=True,
    )
    st.caption(
        f"{crop}　{stage}　{area}亩{loc_txt}　提交于 {create}{farmer_txt}{contact_txt}"
    )
    if symptoms:
        st.caption(f"农户描述　{symptoms[:150]}")
    st.divider()

    # 详情展开
    expanded = task["status"] in (STATUS_PENDING, STATUS_PROCESSING)
    with st.expander("详情与审核操作", expanded=expanded):
        _render_task_detail(task, tid)


def _render_task_detail(task: dict, tid: str) -> None:
    col_left, col_right = st.columns([1, 1.3], gap="large")

    # ========== 左侧：农户上报信息（只读） ==========
    with col_left:
        st.markdown("### 农户图片")
        img_bytes = memory.get_task_image_bytes(tid)
        if img_bytes:
            try:
                st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
            except Exception:
                st.info("图片已损坏")
        else:
            st.info("农户未上传图片")

        st.markdown("### 智能诊断结果")
        ai = task.get("ai_result", {})
        ai_content = ai.get("content", "_无诊断内容_")
        from components.markdown_helper import plain_report_html
        st.markdown(plain_report_html(ai_content), unsafe_allow_html=True)

        st.markdown("### 工单信息")
        info_rows = [
            ("工单编号", _short_id(tid)),
            ("农户名称", task.get("farmer_name", "") or "未填写"),
            ("联系电话", task.get("contact", "") or "未填写"),
            ("地块名称", ((task.get("plot_key", "") or "").replace("::", "　").replace("·", " ")) or "未填写"),
            ("位置", (task.get("location", "") or "").replace("·", " ") or "未填写"),
            ("作物", task.get("crop", "")),
            ("面积", f"{task.get('area', 0)} 亩"),
            ("土壤", task.get("soil_type", "") or "未填写"),
            ("生育阶段", ((task.get("growth_stage") or "").replace("—", "")) or "未填写"),
            ("提交时间", fmt_cn_time(task.get("create_time", ""))),
            ("风险等级", ai.get("risk_level", "未知")),
            ("农户描述", task.get("symptoms", "") or "未填写"),
        ]
        rows_html = "".join(
            f'<div style="display:flex;justify-content:space-between;gap:0.8rem;'
            f'border-bottom:1px dashed #eef2f6;padding:0.3rem 0;">'
            f'<span style="color:#90a4ae;font-size:0.76rem;flex-shrink:0;">{label}</span>'
            f'<span style="color:#2c3e50;font-weight:600;font-size:0.82rem;text-align:right;">{value}</span>'
            f'</div>'
            for label, value in info_rows
        )
        st.markdown(
            f'<div class="ag-rpt-section" style="padding:0.7rem 0.9rem;">'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;column-gap:1.4rem;">'
            f'{rows_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # ========== 右侧：农技员审核区 ==========
    with col_right:
        # ---- 智能诊断预览（只读 · 正式报告形式） ----
        st.markdown("### 智能诊断预览")
        from components.markdown_helper import plain_report_html as _prh
        st.markdown(_prh(ai_content if ai_content.strip() else ""), unsafe_allow_html=True)

        # ---- 农技员审核修改 ----
        st.markdown("### 农技员审核修改")

        reviewer = st.text_input(
            "审核人",
            value=task.get("reviewer", "") or st.session_state.get("tech_name", ""),
            key=f"reviewer_{tid}",
        )

        final_diagnosis = st.text_area(
            "最终诊断结论",
            value=task.get("final_diagnosis", ""),
            height=160,
            placeholder="基于上方智能诊断，填写审核后的正式结论。留空表示沿用系统结果。",
            key=f"diag_{tid}",
        )
        if final_diagnosis.strip():
            _render_md_preview("诊断结论预览", final_diagnosis)

        final_recommendation = st.text_area(
            "最终防治建议",
            value=task.get("final_recommendation", ""),
            height=200,
            placeholder="填写经过安全审核的正式防治建议　药剂选型 剂量 施药时机 注意事项……",
            key=f"rec_{tid}",
        )
        if final_recommendation.strip():
            _render_md_preview("防治建议预览", final_recommendation)

        review_notes = st.text_area(
            "审核备注（内部）",
            value=task.get("review_notes", ""),
            height=80,
            placeholder="记录审核过程 与系统结果的差异 是否需要复查……",
            key=f"notes_{tid}",
        )

        st.divider()

        btn1, btn2, btn3, btn4 = st.columns(4)

        with btn1:
            if st.button("保存审核", key=f"btn_save_{tid}"):
                ok = memory.save_task_review(
                    tid, reviewer=reviewer.strip(),
                    final_diagnosis=final_diagnosis.strip(),
                    final_recommendation=final_recommendation.strip(),
                    review_notes=review_notes.strip(),
                )
                if ok:
                    st.success("已保存审核，工单状态更新为审核中")
                    st.rerun()
                else:
                    st.error("保存失败")

        with btn2:
            if st.button("发布给农户", key=f"btn_pub_{tid}"):
                if not final_diagnosis.strip() and not final_recommendation.strip():
                    st.error("发布前请先填写诊断结论或防治建议")
                else:
                    ok = memory.publish_task(tid)
                    if ok:
                        st.success("建议已发布，工单状态更新为已发布")
                        st.rerun()
                    else:
                        st.error("发布失败")

        with btn3:
            if st.button("关闭工单", key=f"btn_close_{tid}"):
                ok = memory.close_task(tid)
                if ok:
                    st.info("工单已关闭")
                    st.rerun()

        with btn4:
            if st.button("删除", key=f"btn_del_{tid}"):
                ok = memory.delete_task(tid)
                if ok:
                    st.warning("工单已删除")
                    st.rerun()

        if task.get("status") == STATUS_COMPLETED and task.get("publish_time"):
            st.success(f"已于 {fmt_cn_time(task['publish_time'])} 发布给农户")

        if task.get("status") == STATUS_CLOSED and task.get("close_time"):
            st.info(f"已于 {fmt_cn_time(task['close_time'])} 完成归档")

        st.divider()
        st.markdown("### 处理流转")
        published = bool(task.get("publish_time"))
        reviewing = task["status"] in (STATUS_PROCESSING, STATUS_COMPLETED, STATUS_CLOSED)
        flow_steps = [
            ("农户提交", "done"),
            ("AI分析", "done"),
            ("专家审核", "done" if (reviewing or published) else "current"),
            ("方案发布", "done" if published else ("current" if reviewing else "pending")),
        ]
        st.markdown(flow_steps_html(flow_steps), unsafe_allow_html=True)
        st.caption(
            f"提交时间　{fmt_cn_time(task.get('create_time', ''))}"
            + (f"　发布给农户　{fmt_cn_time(task['publish_time'])}" if published else "")
        )
