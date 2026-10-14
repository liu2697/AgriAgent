"""
统计图表组件（自绘 HTML）。

为什么不用 `st.bar_chart`：
    Streamlit 内置柱状图在分类轴放不下长中文标签（如「玉米大斑病」「马铃薯晚疫病」），
    会自动把标签旋转成竖排，既难读又显得排版凌乱（用户实测反馈）。
    自绘横向条形图可以让标签始终水平、完整显示，并与主题里已有的
    `.ag-adm-bar-*` 风格保持一致。
"""
from __future__ import annotations

import html

# 风险等级配色（与 admin_dashboard / theme 保持一致）
RISK_COLORS = {
    "高": "#c0392b",
    "较高": "#c0392b",
    "中": "#e67e22",
    "低": "#1976d2",
    "无": "#2e7d32",
    "未知": "#90a4ae",
}

_PALETTE = ["#1F6B45", "#0d5c63", "#3f7d5c", "#5b8c74", "#78909c",
            "#8d6e63", "#6d4c41", "#00838f", "#558b2f", "#ef6c00"]


def hbar_html(rows: list[tuple[str, float]], *,
              unit: str = "", colors: dict | None = None,
              show_pct: bool = True, empty_hint: str = "暂无数据") -> str:
    """横向条形图。

    参数：
        rows      [(标签, 数值), ...]，按传入顺序展示（调用方负责排序）
        unit      数值单位（如 "次"）
        colors    标签 → 颜色 的映射（如风险等级配色）
        show_pct  是否显示占比
        empty_hint 无数据时的提示文案
    """
    rows = [(str(k), float(v)) for k, v in (rows or [])]
    if not rows:
        return f'<div class="ag-chart-empty">{html.escape(empty_hint)}</div>'

    total = sum(v for _, v in rows) or 1.0
    max_v = max(v for _, v in rows) or 1.0
    colors = colors or {}

    out = ['<div class="ag-chart">']
    for i, (label, value) in enumerate(rows):
        # 条长按最大值归一，便于横向比较；占比另列为参考
        width = max(2.0, value / max_v * 100.0)
        pct = value / total * 100.0
        color = colors.get(label) or _PALETTE[i % len(_PALETTE)]
        pct_html = f'<span class="ag-chart-pct">{pct:.1f}%</span>' if show_pct else ""
        out.append(
            f'<div class="ag-chart-row">'
            f'<div class="ag-chart-lbl" title="{html.escape(label)}">{html.escape(label)}</div>'
            f'<div class="ag-chart-track">'
            f'<div class="ag-chart-fill" style="width:{width:.2f}%;background:{color};"></div>'
            f'</div>'
            f'<div class="ag-chart-val">{value:g}{html.escape(unit)}</div>'
            f'{pct_html}'
            f'</div>'
        )
    out.append("</div>")
    return "".join(out)


__all__ = ["hbar_html", "RISK_COLORS"]
