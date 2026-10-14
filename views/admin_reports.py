"""农技员端 · 报告导出。"""
from datetime import datetime

import streamlit as st

from memory import history as memory
from services import reporting


def render() -> None:
    st.subheader("报告导出")
    st.caption("基于历史诊断与地块档案数据，一键生成植保监测报告。")

    if not memory.get_all_records():
        st.info("暂无数据可导出。农户端完成诊断后可生成报告。")
        return

    md = reporting.build_markdown_report()
    today = datetime.now().strftime("%Y%m%d")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "下载报告（文档格式）",
            data=md.encode("utf-8"),
            file_name=f"农智链AgriAgent_植保监测报告_{today}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with c2:
        try:
            pdf = reporting.build_pdf_report()
            st.download_button(
                "下载报告（PDF 格式）",
                data=pdf,
                file_name=f"农智链AgriAgent_植保监测报告_{today}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            st.error("PDF 生成失败，请确认系统环境依赖")

    with st.expander("报告内容预览", expanded=True):
        st.markdown(md)
