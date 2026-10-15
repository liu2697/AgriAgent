"""农技员监测报告生成：Markdown + PDF（PDF 依赖 reportlab）。"""
from __future__ import annotations

import io
from datetime import datetime

from memory import history as memory
from services import stats
from components.layout import fmt_cn_time
from timeutil import now_cn


def _fmt_time() -> str:
    return now_cn().strftime("%Y-%m-%d %H:%M")


def _md_escape(text: str) -> str:
    """转义 Markdown 表格特殊字符。"""
    return (text or "").replace("|", "／").replace("\n", " ")


def build_markdown_report() -> str:
    """生成 Markdown 格式的植保监测报告。"""
    ov = stats.overview()
    lines = [
        "# 农智链 AgriAgent 农技员植保监测报告",
        "",
        f"> 生成时间　{_fmt_time()}　数据来源　系统诊断记录",
        "",
        "## 一　数据总览",
        "",
        f"- 地块档案数　{ov['plots']} 个",
        f"- 累计诊断次数　{ov['total_visits']} 次",
        f"- 覆盖作物　{ov['crops']} 种（{' '.join(ov['crop_names']) or '暂无'}）",
        f"- 近 7 天诊断　{ov['last7']} 次",
        f"- 高风险记录　{ov['high_risk']} 条（占比 {ov['high_ratio']}%）",
        f"- 最近诊断时间　{fmt_cn_time(ov['last_time'])}",
        "",
        "## 二　病害统计",
        "",
        "| 病害 | 出现次数 |",
        "| --- | --- |",
    ]
    for d in stats.disease_distribution()[:10]:
        lines.append(f"| {_md_escape(d['病害'])} | {d['次数']} |")

    lines += ["", "## 三　风险等级统计", ""]
    lines += ["| 风险等级 | 记录数 |", "| --- | --- |"]
    for r in stats.risk_distribution():
        lines.append(f"| {r['风险等级']} | {r['次数']} |")

    lines += ["", "## 四　地块档案", ""]
    lines += ["| 地块 | 作物 | 面积(亩) | 诊断次数 | 最近诊断 | 最近风险 |", "| --- | --- | --- | --- | --- | --- |"]
    for p in memory.list_plots():
        lines.append(
            f"| {_md_escape(p['location'] or '未命名地块')} | {p['crop']} | {p['area']} | {p['visits']} "
            f"| {fmt_cn_time(p['last_time'])} | {p['last_risk']} |"
        )

    lines += ["", "## 五　近期诊断记录（最近 20 条）", ""]
    lines += ["| 时间 | 地块 | 作物 | 阶段 | 风险 | 诊断摘要 |", "| --- | --- | --- | --- | --- | --- |"]
    for r in memory.get_all_records(limit=20):
        lines.append(
            f"| {fmt_cn_time(r['timestamp'])} | {_md_escape(r.get('location') or '未命名地块')} | {r.get('crop', '')} "
            f"| {r.get('growth_stage', '')} | {r.get('risk_level') or '未知'} "
            f"| {_md_escape((r.get('diagnosis_summary', '') or '')[:30])} |"
        )

    lines += [
        "",
        "---",
        "*本报告由农智链 AgriAgent 智能体自动生成，仅供参考；实际防治请咨询当地农技推广人员。*",
        "",
    ]
    return "\n".join(lines)


def build_pdf_report() -> bytes:
    """生成 PDF 格式报告（需要 reportlab，支持中文）。"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("未安装 reportlab，请执行：pip install reportlab") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
        title="农智链 AgriAgent 农技员植保监测报告",
    )

    title_style = ParagraphStyle(
        "title", fontName="STSong-Light", fontSize=20, leading=26,
        spaceAfter=8, alignment=1,
    )
    meta_style = ParagraphStyle(
        "meta", fontName="STSong-Light", fontSize=9, leading=13,
        textColor=colors.HexColor("#555555"), alignment=1, spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "h2", fontName="STSong-Light", fontSize=14, leading=20,
        spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#2e7d32"),
    )
    body_style = ParagraphStyle(
        "body", fontName="STSong-Light", fontSize=10, leading=16,
    )
    cell_style = ParagraphStyle(
        "cell", fontName="STSong-Light", fontSize=8.5, leading=12,
    )
    head_style = ParagraphStyle(
        "head", fontName="STSong-Light", fontSize=9, leading=12,
        textColor=colors.white,
    )

    story = [
        Paragraph("农智链 AgriAgent 农技员植保监测报告", title_style),
        Paragraph(f"生成时间　{_fmt_time()}　数据来源　系统诊断记录", meta_style),
    ]

    ov = stats.overview()
    story.append(Paragraph("一　数据总览", h2_style))
    story.append(Paragraph(
        f"地块档案 {ov['plots']} 个　累计诊断 {ov['total_visits']} 次　"
        f"覆盖作物 {ov['crops']} 种　近 7 天诊断 {ov['last7']} 次　"
        f"高风险记录 {ov['high_risk']} 条（占比 {ov['high_ratio']}%）　"
        f"最近诊断时间　{fmt_cn_time(ov['last_time'])}",
        body_style,
    ))

    def make_table(headers: list[str], rows: list[list]) -> Table:
        data = [[Paragraph(h, head_style) for h in headers]]
        for row in rows:
            data.append([Paragraph(str(c)[:40], cell_style) for c in row])
        width = doc.width / max(len(headers), 1)
        table = Table(data, colWidths=[width] * len(headers), repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e7d32")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f9f5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return table

    story.append(Paragraph("二　病害统计", h2_style))
    story.append(make_table(
        ["病害", "出现次数"],
        [[d["病害"], d["次数"]] for d in stats.disease_distribution()[:10]],
    ))

    story.append(Paragraph("三　风险等级统计", h2_style))
    story.append(make_table(
        ["风险等级", "记录数"],
        [[r["风险等级"], r["次数"]] for r in stats.risk_distribution()],
    ))

    story.append(Paragraph("四　地块档案", h2_style))
    story.append(make_table(
        ["地块", "作物", "面积(亩)", "次数", "最近诊断", "最近风险"],
        [
            [p["location"] or "未命名地块", p["crop"], p["area"], p["visits"],
             fmt_cn_time(p["last_time"]), p["last_risk"]]
            for p in memory.list_plots()
        ],
    ))

    story.append(Paragraph("五　近期诊断记录（最近 20 条）", h2_style))
    story.append(make_table(
        ["时间", "地块", "作物", "阶段", "风险", "诊断摘要"],
        [
            [fmt_cn_time(r["timestamp"]), r.get("location") or "未命名地块", r.get("crop", ""),
             r.get("growth_stage", ""), r.get("risk_level") or "未知",
             (r.get("diagnosis_summary", "") or "")[:30]]
            for r in memory.get_all_records(limit=20)
        ],
    ))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "本报告由农智链 AgriAgent 智能体自动生成，仅供参考；实际防治请咨询当地农技推广人员。",
        meta_style,
    ))

    doc.build(story)
    return buf.getvalue()


__all__ = ["build_markdown_report", "build_pdf_report"]
