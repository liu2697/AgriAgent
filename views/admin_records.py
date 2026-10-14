"""农技员端 · 历史诊断记录。"""
import streamlit as st

from memory import history as memory
from services import stats


def render() -> None:
    st.subheader("历史诊断记录")
    st.caption("农户端上报的全部诊断记录，支持按作物 风险等级 地块筛选。")

    all_records = memory.get_all_records()
    if not all_records:
        st.info("暂无历史诊断记录。农户端完成诊断后自动生成。")
        return

    f1, f2, f3 = st.columns(3)
    crop = f1.selectbox(
        "筛选作物",
        ["全部"] + sorted({r.get("crop", "") or "未知" for r in all_records}),
    )
    risk = f2.selectbox("筛选风险等级", ["全部", "高", "中", "低", "无", "未知"])
    loc_kw = f3.text_input("地块关键词", placeholder="如 河北")

    rows = stats.recent_table(0)
    if crop != "全部":
        rows = [r for r in rows if r["作物"] == crop]
    if risk != "全部":
        rows = [r for r in rows if r["风险等级"] == risk]
    if loc_kw:
        rows = [r for r in rows if loc_kw in r["地块位置"]]

    st.markdown(f"共 {len(rows)} 条记录，累计 {len(all_records)} 条")
    st.dataframe(rows, use_container_width=True, hide_index=True)
