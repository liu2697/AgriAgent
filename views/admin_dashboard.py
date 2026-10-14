"""
农技员端 · 管理驾驶舱 Dashboard（比赛截图专用版）。

设计方向：农业数字化平台 / 政府农业监管风格
- 渐变 Header + 4 列 KPI + 风险分析 + 重点关注 + AI 摘要
- 所有数据来自 services.stats，零新增 Agent / LLM 调用
"""
from __future__ import annotations

import streamlit as st

from config import APP_NAME, APP_SUBTITLE
from components.charts import RISK_COLORS, hbar_html
from services import stats


RISK_COLOR = {
    "高": "#c0392b", "较高": "#e67e22", "中": "#e67e22",
    "低": "#1F6B45", "无": "#2e7d32", "未知": "#78909c",
}
RISK_CLS = {"高": "risk-high", "较高": "risk-high", "中": "risk-mid",
            "低": "risk-low", "无": "", "未知": ""}


def render() -> None:
    # =========================================================
    # Header — 复用 .ag-rpt-header 深绿渐变风格
    # =========================================================
    ov = stats.overview()
    total_visits = ov["total_visits"]
    high_risk = ov["high_risk"]
    risk_plots = sum(1 for r in stats.plot_summaries()
                     if (r.get("last_risk") or "") in ("高", "较高", "中"))

    st.markdown(
        f"""
        <div class="ag-rpt-header">
            <span class="ag-rpt-hd-badge">农业智能监测中心</span>
            <div class="ag-rpt-hd-title">{APP_NAME}</div>
            <div class="ag-rpt-hd-sub">{APP_SUBTITLE}</div>
            <div class="ag-rpt-hd-tags">
                <span class="ag-rpt-hd-tag">累计诊断 {total_visits} 次</span>
                <span class="ag-rpt-hd-tag">已接入地块 {ov['plots']} 个</span>
                <span class="ag-rpt-hd-tag">高风险记录 {high_risk} 条</span>
                <span class="ag-rpt-hd-tag">建档农户 {ov['farmers']} 户</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =========================================================
    # 系统能力覆盖（先讲能力，再讲当前数据 —— 避免评委把
    # "当前业务数据量"误读成"系统能力上限"）
    # =========================================================
    _render_capability()

    # =========================================================
    # 当前业务运行数据（4 列）
    # =========================================================
    st.markdown("##### 当前业务运行数据")

    st.markdown(
        """
        <div class="ag-adm-note">
            <span class="ag-adm-note-tag">说明</span>
            <div>下列指标为<b>当前系统已接入农户产生的业务数据</b>，
            随农户端持续使用<b>实时更新</b>，不代表系统管理能力上限。
            上方「农业知识能力」为平台已内置的知识与登记数据覆盖范围。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kpis = [
        {"num": ov["plots"], "unit": "个", "lbl": "当前接入地块",
         "hint": "已有诊断记录的地块", "accent": "#1F6B45"},
        {"num": total_visits, "unit": "条", "lbl": "累计诊断记录",
         "hint": f"近 7 日新增 {ov['last7']} 条", "accent": "#0d5c63"},
        {"num": ov["crops"], "unit": "类", "lbl": "当前涉及作物",
         "hint": "已产生诊断记录的作物", "accent": "#6d4c41"},
        {"num": risk_plots, "unit": "个", "lbl": "待关注风险地块",
         "hint": f"其中高风险记录 {high_risk} 条", "accent": "#e67e22"},
    ]

    cards_html = []
    for k in kpis:
        cards_html.append(
            f'<div class="ag-adm-kpi" style="--kpi-accent: {k["accent"]};">'
            f'<div class="ag-adm-kpi-num">{k["num"]}<sub>{k["unit"]}</sub></div>'
            f'<div class="ag-adm-kpi-lbl">{k["lbl"]}</div>'
            f'<div class="ag-adm-kpi-hint">{k["hint"]}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div class="ag-adm-kpi-grid">{"".join(cards_html)}</div>',
        unsafe_allow_html=True,
    )

    if total_visits == 0:
        st.info("暂无诊断数据，请先在农户端完成至少一次诊断")
        return

    # =========================================================
    # 病害风险分析 — 左右分栏
    # =========================================================
    st.markdown("##### 病害风险分析")

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        st.markdown("**主要病害分布**")
        dist = stats.disease_distribution()
        # 横向条形图：st.bar_chart 在分类轴放不下「玉米大斑病」这类长中文标签，
        # 会旋转成竖排（用户实际截图反馈）。改用自绘横向条形，标签始终水平。
        st.markdown(
            hbar_html([(d["病害"], d["次数"]) for d in dist], unit="", show_pct=True,
                      empty_hint="暂无病害识别记录"),
            unsafe_allow_html=True,
        )

    with col_right:
        st.markdown("**风险等级统计**")
        risk_dist = stats.risk_distribution()
        st.markdown(
            hbar_html([(r["风险等级"], r["次数"]) for r in risk_dist],
                      unit="", colors=RISK_COLORS, show_pct=True),
            unsafe_allow_html=True,
        )

    # =========================================================
    # 重点关注地块列表
    # =========================================================
    st.markdown("##### 重点关注地块")

    rows = stats.risk_plot_table()
    if rows:
        table_rows = []
        for r in rows[:8]:
            level = r.get("风险等级", "未知")
            cls = RISK_CLS.get(level, "")
            level_color = RISK_COLOR.get(level, "#78909c")
            crop = r.get("作物", "")
            plot_loc = r.get("地块位置", "")
            diag = (r.get("最近诊断", "") or "")[:40]
            table_rows.append(
                f'<tr class="{cls}">'
                f'<td>{plot_loc}</td>'
                f'<td>{crop}</td>'
                f'<td style="color:{level_color};font-weight:600;">{level}</td>'
                f'<td style="color:#78909c;font-size:0.68rem;">{diag}</td>'
                f'</tr>'
            )

        st.markdown(
            f"""
            <div style="overflow-x:auto;">
            <table class="ag-adm-tbl">
                <thead>
                <tr>
                    <th>地块</th>
                    <th>作物</th>
                    <th>风险</th>
                    <th>最近诊断</th>
                </tr>
                </thead>
                <tbody>
                {"".join(table_rows)}
                </tbody>
            </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

        high_count = sum(1 for r in rows if r.get("风险等级") in ("高", "较高"))
        if high_count:
            st.warning(f"{high_count} 个高/较高风险地块，建议优先安排田间复核")
        else:
            st.success("当前无高/较高风险地块，田间整体态势良好")
    else:
        st.info("暂无地块档案数据")

    # =========================================================
    # AI 风险分析摘要（复用已有数据生成自然语言）
    # =========================================================
    st.markdown("##### 监测分析摘要")

    summary = _build_summary(ov, stats)
    st.markdown(
        f"""
        <div class="ag-adm-summary">
            <div class="ag-adm-summary-title">
                农智链 AgriAgent　智能分析
            </div>
            <div class="ag-adm-summary-body">
                {summary}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================================
# 系统能力覆盖（真实读取知识库 / 农药登记库，不写死数字）
# =========================================================================

def _render_capability() -> None:
    """展示平台"能力覆盖"。

    为什么单独放一块：评委看到"当前接入地块 6 个 / 涉及作物 3 类"很容易
    误读成"系统只能管 6 个地块、只支持 3 种作物"。这里把
    **知识与登记数据的覆盖范围** 与 **当前业务数据量** 明确分开，
    并把数据来源一并写明，避免追问时无从解释。

    所有数字均实时读取知识库，新增作物/病害后自动更新，不做硬编码。
    """
    from knowledge_center.loader import load_diseases
    from knowledge_center.registration import load_registry

    try:
        diseases = load_diseases()
        crops = sorted({str(e.get("crop")) for e in diseases if e.get("crop")})
        diseases_n = len(diseases)
    except Exception:
        crops, diseases_n = [], 0

    try:
        registry_n = len(load_registry())
    except Exception:
        registry_n = 0

    from config import CROPS as _CROPS
    selectable = len(_CROPS)

    items = [
        {"num": len(crops), "unit": "类", "lbl": "知识库覆盖作物",
         "hint": "、".join(crops) if crops else "—"},
        {"num": diseases_n, "unit": "条", "lbl": "结构化病虫害知识条目",
         "hint": "含症状 / 发生条件 / 诊断特征 / 防治方案"},
        {"num": selectable, "unit": "种", "lbl": "农户端可选作物",
         "hint": "北方大田主栽作物 + 其他"},
        {"num": registry_n, "unit": "个", "lbl": "农药登记数据",
         "hint": "农业农村部公告导入（含登记作物与防治对象）"},
    ]

    cards = []
    for it in items:
        cards.append(
            f'<div class="ag-adm-capab-item">'
            f'<div class="ag-adm-capab-num">{it["num"]}<sub>{it["unit"]}</sub></div>'
            f'<div class="ag-adm-capab-lbl">{it["lbl"]}</div>'
            f'<div class="ag-adm-capab-hint">{it["hint"]}</div>'
            f'</div>'
        )

    st.markdown(
        f"""
        <div class="ag-adm-capab">
            <div class="ag-adm-capab-title">农业知识能力（平台已内置范围）</div>
            <div class="ag-adm-capab-sub">
                以下为知识库与农药登记数据的实际覆盖范围，与当前接入的业务数据量无关
            </div>
            <div class="ag-adm-capab-grid">{"".join(cards)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================================
# AI 风险分析摘要 — 纯规则生成，零 LLM 调用
# =========================================================================

def _build_summary(ov: dict, stats_mod) -> str:
    """基于已有统计数据生成自然语言摘要。"""
    total = ov["total_visits"]
    plots = ov["plots"]
    high = ov["high_risk"]
    high_pct = ov["high_ratio"]
    farmers = ov["farmers"]

    # 主要病害
    dist = stats_mod.disease_distribution()
    top_diseases = " ".join(d["病害"] for d in dist[:3]) if dist else "暂无明确病害"

    # 作物分布
    crops = stats_mod.crop_distribution()
    top_crop = crops[0]["作物"] if crops else "—"

    # 风险判断
    if high_pct >= 30:
        risk_judge = f"当前处于<span style='color:#ffcdd2;font-weight:700;'>高发预警状态</span>"
    elif high_pct >= 15:
        risk_judge = f"整体<span style='color:#fff59d;font-weight:700;'>风险偏高</span>，需加强巡田"
    elif high > 0:
        risk_judge = "总体可控，但存在局部高风险"
    else:
        risk_judge = "整体态势良好，暂无大面积病害"

    return (
        f"系统当前已接入 <b>{plots}</b> 个地块、<b>{farmers}</b> 户农户，"
        f"累计完成 <b>{total}</b> 次智能诊断。"
        f"<br>当前诊断涉及作物以 <b>{top_crop}</b> 为主，"
        f"高频病害为 <b>{top_diseases}</b>。"
        f"<br>高风险记录 <b>{high}</b> 条（占比 {high_pct}%），{risk_judge}。"
        f"<br>说明：以上为当前已接入业务的实时统计；平台知识库与农药登记数据"
        f"的覆盖范围见上方「农业知识能力」。"
        f"<br>建议农技员重点关注高风险地块，结合实地勘察与系统建议出具正式处置方案。"
    )
