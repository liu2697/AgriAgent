# -*- coding: utf-8 -*-
"""统一的导出按钮组：Word / PDF / 纯文本。

为什么单独抽出来：
  · 农户端「导出记录」与「下载最终方案」都要这三种格式，避免每处各写一遍；
  · python-docx / reportlab 缺失时给出**诚实的不可用提示**，而不是静默失败或伪造空文件。
"""
from __future__ import annotations

import streamlit as st

from components.markdown_helper import strip_md

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def render_export_buttons(text: str, *, stem: str, key_prefix: str) -> None:
    """渲染「导出纯文本 / 导出 Word / 导出 PDF」三个按钮。

    text       : 要导出的正文（Markdown 或纯文本均可）
    stem       : 文件名主体（不含扩展名）
    key_prefix : Streamlit 元素 key 前缀（同页多次调用必须不同）
    """
    body = (text or "").strip()
    if not body:
        st.caption("暂无可导出的内容。")
        return

    cols = st.columns(3)

    with cols[0]:
        st.download_button(
            "导出纯文本", data=strip_md(body).encode("utf-8"),
            file_name=f"{stem}.txt", mime="text/plain",
            use_container_width=True, key=f"{key_prefix}_txt",
        )

    with cols[1]:
        try:
            from services.plan_export import build_plan_docx
            st.download_button(
                "导出 Word", data=build_plan_docx(body, title=stem),
                file_name=f"{stem}.docx", mime=_DOCX_MIME,
                use_container_width=True, key=f"{key_prefix}_docx",
            )
        except Exception as exc:  # noqa: BLE001  缺库/异常时诚实提示，不伪造文件
            st.button("导出 Word（不可用）", disabled=True,
                      use_container_width=True, key=f"{key_prefix}_docx_off")
            st.caption(f"Word 导出不可用：{exc}")

    with cols[2]:
        try:
            from services.plan_export import build_plan_pdf
            st.download_button(
                "导出 PDF", data=build_plan_pdf(body, title=stem),
                file_name=f"{stem}.pdf", mime="application/pdf",
                use_container_width=True, key=f"{key_prefix}_pdf",
            )
        except Exception as exc:  # noqa: BLE001
            st.button("导出 PDF（不可用）", disabled=True,
                      use_container_width=True, key=f"{key_prefix}_pdf_off")
            st.caption(f"PDF 导出不可用：{exc}")
