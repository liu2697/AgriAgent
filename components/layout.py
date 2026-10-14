"""
统一页面布局 / 壳组件。

封装"页面头部 + 侧边栏导航 + 页脚"三要素，
并提供统一的中文时间格式与信息卡组件。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Tuple

import streamlit as st

from config import APP_NAME, APP_SUBTITLE, APP_VERSION
from components.theme import DEFAULT_THEME


def fmt_cn_time(ts: str) -> str:
    """将 ISO 时间转换为中文格式：2026-09-26T04:24 → 2026年9月26日 04:24。"""
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts[:19])
    except (ValueError, TypeError):
        return ts[:16]
    return f"{dt.year}年{dt.month}月{dt.day}日 {dt:%H:%M}"


def info_card_html(label: str, value: str) -> str:
    """信息卡组件：标签在上、值在下。"""
    return (
        f'<div class="ag-info-card">'
        f'<div class="ag-info-lbl">{label}</div>'
        f'<div class="ag-info-val">{value}</div>'
        f'</div>'
    )


def info_grid_html(cards: List[Tuple[str, str]]) -> str:
    """信息卡网格：[(标签, 值), ...] → 卡片化布局。"""
    return f'<div class="ag-info-grid">{"".join(info_card_html(l, v) for l, v in cards)}</div>'


# ---------------------------------------------------------------------------
# 业务闭环：工单状态展示映射 + 步骤流转条
# ---------------------------------------------------------------------------

TASK_STATUS_DISPLAY = {
    "待审核": "待审核",
    "处理中": "审核中",
    "已完成": "已发布",
    "已关闭": "已完成",
}


def task_status_display(status: str) -> str:
    """将内部工单状态映射为面向用户的流转名称。"""
    return TASK_STATUS_DISPLAY.get(status, status)


def flow_steps_html(steps: List[Tuple[str, str]], vertical: bool = False) -> str:
    """步骤流转条：[(标签, 状态)]，状态 ∈ done / current / pending。"""
    parts = []
    for i, (label, state) in enumerate(steps):
        cls = state if state in ("done", "current") else "pending"
        mark = "✓" if cls == "done" else str(i + 1)
        parts.append(
            f'<div class="ag-fs-step">'
            f'<div class="ag-fs-dot {cls}">{mark}</div>'
            f'<div class="ag-fs-label {cls}">{label}</div>'
            f'</div>'
        )
        if i < len(steps) - 1:
            parts.append(f'<div class="ag-fs-arrow">{"↓" if vertical else "→"}</div>')
    wrap = "ag-fs-v" if vertical else "ag-fs"
    return f'<div class="{wrap}">{"".join(parts)}</div>'


RISK_BADGE = {
    "高":  ("ag-badge-danger",  "● 高风险"),
    "中":  ("ag-badge-warning", "● 中风险"),
    "低":  ("ag-badge-info",    "● 低风险"),
    "无":  ("ag-badge-success", "● 无风险"),
    "未知": ("ag-badge-muted",  "● 未知"),
}


def risk_badge_html(level: str) -> str:
    cls, label = RISK_BADGE.get(level, RISK_BADGE["未知"])
    return f'<span class="ag-badge {cls}">{label}</span>'


def page_header(title: str, subtitle: str = "", breadcrumb: Optional[List[str]] = None) -> None:
    """
    统一页面头部。
    - 简洁标题（非 Banner）
    - 可选面包屑
    - 底部 1px 分隔线
    """
    parts = []
    if breadcrumb:
        crumb_html = " <span style='color:#b0bec5'>/</span> ".join(
            f"<span>{b}</span>" for b in breadcrumb
        )
        parts.append(
            f'<div style="font-size:0.78rem;color:#90a4ae;margin-bottom:0.3rem;">'
            f'{crumb_html}</div>'
        )
    parts.append(f'<h2 class="ag-page-title">{title}</h2>')
    if subtitle:
        parts.append(f'<div class="ag-page-sub">{subtitle}</div>')
    st.markdown(
        f'<div class="ag-page-header">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def section_title(text: str, subtext: str = "") -> None:
    """统一 Section 标题（带左侧绿色竖线）。"""
    html = f'<div class="ag-section-title">{text}</div>'
    if subtext:
        html += f'<div style="font-size:0.8rem;color:#90a4ae;margin-top:-0.25rem;margin-bottom:0.5rem;">{subtext}</div>'
    st.markdown(html, unsafe_allow_html=True)


def stat_card_html(label: str, value: str | int | float,
                   trend: str = "", accent: str = "#1f5f3a") -> str:
    """
    自绘统计卡 HTML（替代 st.metric，样式统一）。
    """
    label_html = f'<div class="ag-card-header">{label}</div>'
    value_html = f'<div class="ag-card-value" style="color:{accent}">{value}</div>'
    trend_html = f'<div class="ag-card-trend">{trend}</div>' if trend else ""
    return (
        f'<div class="ag-card" style="margin-bottom:0.5rem;">'
        f'{label_html}{value_html}{trend_html}</div>'
    )


def render_brand_block() -> None:
    """侧边栏顶部品牌区（替代大面积渐变 Banner）。"""
    st.markdown(
        f"""
        <div style="padding: 0.8rem 0.2rem 1rem 0.2rem; border-bottom: 1px solid #cfd8dc; margin-bottom: 0.5rem;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #1f5f3a; letter-spacing: -0.01em;">
                {APP_NAME}
            </div>
            <div style="font-size: 0.72rem; color: #90a4ae; margin-top: 0.15rem;">
                {APP_SUBTITLE} · v{APP_VERSION}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """统一页脚。"""
    st.markdown(
        f"""
        <div style="text-align:center;padding:1.5rem 0 0.5rem 0;color:#b0bec5;font-size:0.75rem;border-top:1px solid #cfd8dc;margin-top:2rem;">
            {APP_NAME} · {APP_SUBTITLE}
        </div>
        """,
        unsafe_allow_html=True,
    )


__all__ = [
    "page_header",
    "section_title",
    "stat_card_html",
    "risk_badge_html",
    "render_brand_block",
    "render_footer",
    "fmt_cn_time",
    "info_card_html",
    "info_grid_html",
    "task_status_display",
    "flow_steps_html",
]
