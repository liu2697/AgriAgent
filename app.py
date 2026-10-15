"""农智链 AgriAgent 统一入口 — Streamlit + 角色路由 + 组件化布局。"""
import streamlit as st

from config import APP_NAME, APP_SUBTITLE, APP_ICON, APP_VERSION, ADMIN_PASSWORD
from components import (
    inject_theme, render_brand_block, render_footer,
    risk_badge_html,
)
import views.farmer as farmer_view
import views.admin_tasks as admin_tasks
import views.admin_dashboard as admin_dashboard
import views.admin_plots as admin_plots
import views.admin_plan as admin_plan
import views.admin_records as admin_records
import views.admin_diseases as admin_diseases
import views.admin_risks as admin_risks
import views.admin_reports as admin_reports
import views.admin_knowledge as admin_knowledge

st.set_page_config(
    page_title=f"{APP_NAME} · {APP_SUBTITLE}",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()

# ---------------------------------------------------------------------------
# 数据库初始化（SQLite：不存在自动创建，已存在正常复用，不破坏数据）
# ---------------------------------------------------------------------------
try:
    from database.schema import init_db
    init_db()
except Exception as _db_err:  # noqa: BLE001 — 初始化失败不阻断页面启动
    st.warning(f"数据库初始化异常：{_db_err}")

# ---------------------------------------------------------------------------
# 首次启动自动生成演示数据（数据库为空时；已初始化过的库不受影响）
# 用途：Streamlit Community Cloud 等公网部署环境磁盘为临时存储，
#       应用重启后自动重建演示地块/诊断/工单，评委打开即有完整数据。
# ---------------------------------------------------------------------------
try:
    from database.connection import db_scope as _db_scope

    def _demo_db_is_empty() -> bool:
        with _db_scope() as conn:
            farmers = conn.execute("SELECT COUNT(*) FROM farmers").fetchone()[0]
            plots = conn.execute("SELECT COUNT(*) FROM plots").fetchone()[0]
        return farmers == 0 and plots == 0

    if _demo_db_is_empty():
        import generate_demo_data
        generate_demo_data.main()
except Exception as _seed_err:  # noqa: BLE001 — 种子失败不阻断页面启动
    st.warning(f"演示数据生成失败：{_seed_err}")

# ---------------------------------------------------------------------------
# 角色路由
# ---------------------------------------------------------------------------
ROLE_FARMER = "农户端 · 智能生产管理"
ROLE_TECH = "农技员端 · 监测后台"

ADMIN_PAGES = {
    "问题工单管理": admin_tasks.render,
    "数据总览": admin_dashboard.render,
    "地块档案管理": admin_plots.render,
    "生产计划": admin_plan.render,
    "历史诊断记录": admin_records.render,
    "病害统计分析": admin_diseases.render,
    "风险等级统计": admin_risks.render,
    "农业知识中心": admin_knowledge.render,
    "报告导出": admin_reports.render,
}


with st.sidebar:
    render_brand_block()
    role = st.radio("选择角色", [ROLE_FARMER, ROLE_TECH], key="agriagent_role")
    st.divider()

if role == ROLE_FARMER:
    farmer_view.render()
else:
    if "admin_authed" not in st.session_state:
        st.session_state.admin_authed = False  # C-1：初始未认证，必须显式登录

    with st.sidebar:
        if not st.session_state.admin_authed:
            pwd = st.text_input("管理密码", type="password", key="admin_pwd")
            if st.button("登录监测后台", use_container_width=True):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.admin_authed = True
                    st.rerun()
                else:
                    st.error("密码错误")
        else:
            page = st.radio("监测功能", list(ADMIN_PAGES), key="agriagent_admin_page")
            st.divider()
            if st.button("退出登录", use_container_width=True):
                st.session_state.admin_authed = False  # C-1：退出后回到登录态
                st.rerun()
            st.caption(f"{APP_NAME} © {APP_VERSION}")

    if not st.session_state.admin_authed:
        st.markdown(
            """
            <div style="text-align:center;padding:5rem 1rem;">
                <div style="font-size:1.25rem;font-weight:600;color:#1F6B45;margin-bottom:0.4rem;">
                    农技员监测后台
                </div>
                <div style="color:#78909c;font-size:0.88rem;margin-bottom:2rem;">
                    请输入密码
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        ADMIN_PAGES[page]()

render_footer()
