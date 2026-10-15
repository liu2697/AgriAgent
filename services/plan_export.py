"""生产方案导出：PDF（reportlab）与 Word（python-docx）。

## 为什么单独成模块

`components/markdown_helper.py` 只负责把 Markdown 规范化并渲染成 HTML，
不引入重依赖。PDF/Word 生成需要 reportlab / python-docx，且是**导出**专用，
因此放在 services 层，页面按需调用。

## 中文渲染

PDF 用的是 reportlab 自带的 CID 字体 `STSong-Light`（无需附带字体文件），
与 `services/reporting.py` 里农技员监测报告的方案一致，避免引入字体依赖。

## 降级策略

- 未安装 reportlab / python-docx 时抛 `RuntimeError`，由页面捕获后
  只展示可用的导出方式，**不静默失败**。
"""
from __future__ import annotations

import io
import re
from typing import Iterable

from components.markdown_helper import normalize_md, strip_emoji


def _iter_blocks(text: str) -> Iterable[tuple[str, str]]:
    """把规范化后的方案拆成 (类型, 内容) 序列。

    类型：
      - "title"  总标题
      - "head"   分组小标题（第N周 / 阶段）
      - "item"   列表条目
      - "text"   普通段落
    """
    norm = normalize_md(text)
    first_head_done = False
    for raw in norm.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = re.fullmatch(r"\*\*(.+?)\*\*", line)
        if m:
            title = m.group(1)
            if not first_head_done:
                first_head_done = True
                yield ("title", title)
            else:
                yield ("head", title)
            continue
        line = re.sub(r"^\s*\d+[.、)]\s+", "", line)
        line = re.sub(r"^\s*[-+•]\s+", "", line)
        line = re.sub(r"^\s*[*]\s+", "", line)
        if line:
            yield ("item", line)


def _plain(text: str) -> str:
    """去掉行内加粗标记，得到纯文本。"""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", strip_emoji(text)).strip()


def build_plan_pdf(text: str, title: str = "") -> bytes:
    """把方案导出为 PDF（A4，中文，零字体依赖）。"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("未安装 reportlab，请执行：pip install reportlab") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm,
        title=title or "农智链 AgriAgent 生产管理方案",
    )

    st_title = ParagraphStyle("t", fontName="STSong-Light", fontSize=17,
                              leading=24, spaceAfter=4,
                              textColor=colors.HexColor("#1f5f3a"))
    st_head = ParagraphStyle("h", fontName="STSong-Light", fontSize=12.5,
                             leading=19, spaceBefore=11, spaceAfter=5,
                             textColor=colors.HexColor("#0d5c63"))
    st_item = ParagraphStyle("i", fontName="STSong-Light", fontSize=10,
                             leading=17, spaceAfter=2)
    st_note = ParagraphStyle("n", fontName="STSong-Light", fontSize=8.5,
                             leading=13, spaceBefore=12,
                             textColor=colors.HexColor("#8d9aa5"))

    flow = []
    pending_items: list[str] = []

    def flush_items():
        if not pending_items:
            return
        flow.append(ListFlowable(
            [ListItem(Paragraph(_plain(x), st_item), leftIndent=14)
             for x in pending_items],
            bulletType="bullet", bulletFontName="STSong-Light",
            bulletFontSize=8, leftIndent=12,
        ))
        flow.append(Spacer(1, 3))
        pending_items.clear()

    for kind, content in _iter_blocks(text):
        if kind in ("title", "head"):
            flush_items()
            if kind == "title":
                flow.append(Paragraph(_plain(content), st_title))
                flow.append(HRFlowable(width="100%", thickness=1.2,
                                       color=colors.HexColor("#1F6B45"),
                                       spaceBefore=3, spaceAfter=6))
            else:
                flow.append(Paragraph(_plain(content), st_head))
        else:
            pending_items.append(content)
    flush_items()

    flow.append(Paragraph(
        "本方案由农智链 AgriAgent 自动生成，仅供辅助决策参考；"
        "实际农事请结合天气预报与当地农技人员指导。", st_note))

    doc.build(flow)
    return buf.getvalue()


def build_plan_docx(text: str, title: str = "") -> bytes:
    """把方案导出为 Word（.docx，真正可编辑的文档）。"""
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt, RGBColor
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("未安装 python-docx，请执行：pip install python-docx") from exc

    doc = Document()
    # 中文字体：同时设置 ascii/eastasia，否则中文会回退成默认字体
    try:
        from docx.oxml.ns import qn
        style = doc.styles["Normal"]
        style.font.name = "微软雅黑"
        style.font.size = Pt(10.5)
        style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    except Exception:
        pass

    first_head_done = False
    for kind, content in _iter_blocks(text):
        plain = _plain(content)
        if kind == "title":
            h = doc.add_heading(plain, level=0)
            for r in h.runs:
                r.font.color.rgb = RGBColor(0x1F, 0x5F, 0x3A)
        elif kind == "head":
            h = doc.add_heading(plain, level=2)
            for r in h.runs:
                r.font.color.rgb = RGBColor(0x0D, 0x5C, 0x63)
        else:
            # 条目：以「• 」前缀成段，避免依赖 Word 列表样式（跨版本不稳定）
            p = doc.add_paragraph(plain, style="List Bullet")
            p.paragraph_format.space_after = Pt(2)

    doc.add_paragraph()
    note = doc.add_paragraph(
        "本方案由农智链 AgriAgent 自动生成，仅供辅助决策参考；"
        "实际农事请结合天气预报与当地农技人员指导。")
    note.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for r in note.runs:
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(0x8D, 0x9A, 0xA5)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


__all__ = ["build_plan_pdf", "build_plan_docx"]
