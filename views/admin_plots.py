"""农技员端 · 地块档案管理（含地块详情页入口）。"""
import streamlit as st

from components.layout import fmt_cn_time
from memory import history as memory
from memory import profiles
from services import stats
import views.admin_plot_detail as detail_view


def render() -> None:
    # 地块详情页导航：选中地块后进入详情，返回按钮置空后回到列表
    detail_key = st.session_state.get("admin_plot_detail")
    if detail_key:
        detail_view.render(detail_key)
        return

    st.subheader("地块档案管理")
    st.caption("登记各地块的作物 面积与历史病害情况，支持查看详情与生产计划。")

    plots = stats.plot_summaries()
    if not plots:
        st.info("暂无地块档案。农户端完成诊断后系统会自动建档。")
        return

    st.markdown(f"共 {len(plots)} 个地块档案")
    for p in plots:
        loc_txt = p.get("location") or "未命名地块"
        with st.expander(
            f"{loc_txt}　{p['crop']}　{p['area']}亩　最近风险 {p['last_risk']}　识别病害 {p.get('disease', '未识别')}",
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("诊断次数", p["visits"])
            c2.metric("面积", f"{p['area']} 亩")
            c3.metric("首次诊断", fmt_cn_time(p["first_time"]))
            c4.metric("最近诊断", fmt_cn_time(p["last_time"]))

            st.markdown(f"最近诊断摘要　{p.get('last_summary', '') or '暂无'}")
            st.markdown(f"最近建议摘要　{(p.get('last_recommendation', '') or '暂无')[:200]}")

            hist = memory.get_history(p["location"], p["crop"], p["area"], limit=20)
            if hist:
                st.markdown("该地块历史诊断记录")
                for r in reversed(hist):
                    st.caption(
                        f"{fmt_cn_time(r['timestamp'])}　{r['growth_stage']}　"
                        f"风险 {r.get('risk_level') or '未知'}　{r['diagnosis_summary'][:40]}"
                    )

            b1, b2 = st.columns(2)
            with b1:
                if st.button("查看地块详情", key=f"detail_{p['plot_key']}"):
                    st.session_state["admin_plot_detail"] = p["plot_key"]
                    st.rerun()
            with b2:
                if st.button("删除地块档案", key=f"del_{p['plot_key']}"):
                    memory.delete_plot(p["plot_key"])
                    profiles.delete_profile(p["plot_key"])
                    st.success("已删除地块档案")
                    st.rerun()
