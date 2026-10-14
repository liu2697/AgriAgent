"""农技员端 · 农业知识中心管理。"""
from __future__ import annotations

import streamlit as st

from components import page_header, section_title, stat_card_html, risk_badge_html
from knowledge_center.loader import (
    load_diseases, load_pesticides, list_crops,
    save_disease, delete_disease,
)


def render() -> None:
    page_header(
        title="农业知识中心",
        subtitle="浏览结构化病害知识 新增与维护条目 让诊断有据可查",
        breadcrumb=["监测后台", "知识中心"],
    )

    diseases = load_diseases()
    pesticides = load_pesticides()
    crops = list_crops()

    # ======= 顶部：知识库统计 =======
    c1, c2, c3 = st.columns(3)
    c1.markdown(
        stat_card_html("知识条目总数", f"{len(diseases)}", "结构化病害条目", "#1F6B45"),
        unsafe_allow_html=True,
    )
    c2.markdown(
        stat_card_html("覆盖作物", f"{len(crops)}", "/".join(crops) if crops else "暂无", "#0d5c63"),
        unsafe_allow_html=True,
    )
    c3.markdown(
        stat_card_html("农药安全规范", f"{len(pesticides)} 类", "杀菌剂/杀虫剂/禁限用", "#1F6B45"),
        unsafe_allow_html=True,
    )

    st.divider()

    # ======= 左侧 Tab 管理，右侧预览 =======
    tab_search, tab_pesticide, tab_add = st.tabs(
        ["知识检索", "农药安全规范", "新增维护知识"]
    )

    with tab_search:
        _render_search_tab(diseases)

    with tab_pesticide:
        _render_pesticide_tab(pesticides)

    with tab_add:
        _render_add_tab()


# =========================================================================
# Tab 1: 知识检索 + 详情
# =========================================================================

def _render_search_tab(diseases: list[dict]) -> None:
    section_title("知识检索", "按作物 + 关键词筛选，点击条目查看完整详情")

    col_filter1, col_filter2, col_filter3 = st.columns([1, 1, 2])
    with col_filter1:
        crop_filter = st.selectbox("作物筛选", ["全部作物"] + list_crops(), key="kcenter_crop_filter")
    with col_filter2:
        risk_filter = st.selectbox("风险等级", ["全部", "高", "中", "低", "未知"], key="kcenter_risk_filter")
    with col_filter3:
        keyword = st.text_input("关键词搜索（病害名/别名/症状）", value="",
                                placeholder="如 大斑病 水渍 锈病", key="kcenter_keyword")

    filtered = list(diseases)
    if crop_filter != "全部作物":
        filtered = [d for d in filtered if d.get("crop") == crop_filter]
    if risk_filter != "全部":
        filtered = [d for d in filtered if d.get("risk_level", "") == risk_filter]
    if keyword.strip():
        kw = keyword.strip().lower()
        filtered = [
            d for d in filtered
            if kw in (d.get("disease", "") or "").lower()
            or kw in " ".join(d.get("aliases", [])).lower()
            or kw in " ".join(d.get("symptoms", [])).lower()
        ]

    st.caption(f"匹配到 {len(filtered)} 条")

    if not filtered:
        st.info("暂无匹配条目")
        return

    section_title("知识详情", "")

    for i, entry in enumerate(filtered, 1):
        risk = entry.get("risk_level", "未知")
        aliases = entry.get("aliases", []) or []
        risk_badge = risk_badge_html(risk)

        with st.expander(
            f"#{i}　{entry.get('disease', '')}　{entry.get('crop', '')}　风险等级 {risk}",
            expanded=(i == 1),
        ):
            col_left, col_right = st.columns([1.2, 1])

            with col_left:
                st.markdown("##### 基本信息")
                if aliases:
                    st.markdown(f"别名　{' '.join(aliases)}")
                st.markdown(f"作物　{entry.get('crop', '')}")
                st.markdown(f"风险等级　{risk_badge}", unsafe_allow_html=True)

                st.markdown("##### 典型症状")
                for s in entry.get("symptoms", []) or []:
                    st.markdown(f"- {s}")

                st.markdown("##### 发生条件")
                for c in entry.get("occurrence_conditions", []) or []:
                    st.markdown(f"- {c}")

            with col_right:
                st.markdown("##### 诊断特征")
                for f in entry.get("diagnosis_features", []) or []:
                    st.markdown(f"- {f}")

                st.markdown("##### 防治建议")
                for p in entry.get("prevention", []) or []:
                    st.markdown(f"- {p}")

                pr = entry.get("pesticide_reference") or {}
                if pr:
                    st.markdown("##### 农药参考")
                    if pr.get("registered"):
                        st.markdown(f"登记药剂　{' '.join(pr['registered'])}")
                    if pr.get("dosage"):
                        st.markdown(f"参考用量　{pr['dosage']}")
                    if pr.get("application_timing"):
                        st.markdown(f"施药时期　{pr['application_timing']}")
                    if pr.get("safety_interval"):
                        st.markdown(f"安全间隔期　{pr['safety_interval']}")

            if st.button("删除此条目", key=f"del_{entry.get('crop')}_{entry.get('disease')}_{i}"):
                ok, msg = delete_disease(entry.get("crop", ""), entry.get("disease", ""))
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


# =========================================================================
# Tab 2: 农药安全规范
# =========================================================================

def _render_pesticide_tab(pesticides: list[dict]) -> None:
    section_title("农药类别与安全规范", "农药类别 登记防治靶标 参考用量与安全间隔期")

    for entry in pesticides:
        if entry.get("category") == "禁限用农药提示":
            st.markdown("##### 国家禁限用农药提示")
            forbidden = entry.get("forbidden_substances", []) or []
            cols = st.columns(min(3, len(forbidden)))
            for i, f in enumerate(forbidden):
                with cols[i % len(cols)]:
                    st.markdown(
                        f'<div style="border-left:3px solid #c0392b;padding:0.4rem 0.7rem;'
                        f'background:#ffebee;border-radius:4px;margin-bottom:0.4rem;">'
                        f'<div style="font-weight:600;color:#c0392b;">{f.get("name","")}</div>'
                        f'<div style="font-size:0.78rem;color:#78909c;margin-top:0.2rem;">'
                        f'{f.get("status","")}</div>'
                        f'<div style="font-size:0.75rem;color:#b0bec5;margin-top:0.15rem;">'
                        f'{f.get("reason","")}</div></div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("##### 安全使用原则")
            for p in entry.get("safety_principles", []) or []:
                st.markdown(f"- {p}")
        else:
            cat = entry.get("category", "其他")
            st.markdown(f"##### {cat}")
            for prod in entry.get("products", []) or []:
                st.markdown(
                    f'<div class="ag-card" style="padding:0.6rem 0.9rem;margin-bottom:0.5rem;">'
                    f'<div style="font-weight:600;color:#0d5c63;">{prod.get("name","")}</div>'
                    f'<div style="font-size:0.78rem;color:#78909c;margin-top:0.2rem;">'
                    f'作用机制　{prod.get("mode","")}</div>'
                    f'<div style="font-size:0.78rem;color:#546e7a;margin-top:0.2rem;">'
                    f'登记防治　{" ".join(prod.get("registered_targets",[]))}</div>'
                    f'<div style="font-size:0.78rem;color:#546e7a;margin-top:0.2rem;">'
                    f'参考用量　{prod.get("typical_dosage","")}　'
                    f'安全间隔期 {prod.get("safety_interval_days","")} 天</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# =========================================================================
# Tab 3: 新增 / 维护
# =========================================================================

def _render_add_tab() -> None:
    section_title("新增病害知识条目", "保存后系统自动加载生效")

    with st.form("add_disease_form"):
        col1, col2 = st.columns(2)
        with col1:
            crop = st.text_input("作物 *", value="", placeholder="如 玉米 水稻 番茄")
            disease = st.text_input("病害名称 *", value="", placeholder="如 玉米大斑病")
            aliases_str = st.text_input("别名（逗号分隔）", value="", placeholder="如 大斑病 玉米叶枯病")
            risk_level = st.selectbox("风险等级", ["低", "中", "高"], index=1)
        with col2:
            symptoms_str = st.text_area("典型症状（每行一条）", value="", height=120,
                                        placeholder="叶片出现褐色长条斑\n病斑呈梭形\n...")
            conditions_str = st.text_area("发生条件（每行一条）", value="", height=100,
                                          placeholder="高温高湿\n连作地块\n...")

        col3, col4 = st.columns(2)
        with col3:
            features_str = st.text_area("诊断特征（每行一条）", value="", height=100,
                                        placeholder="病斑沿叶脉纵向扩展\n...")
            prevention_str = st.text_area("防治方法（每行一条）", value="", height=100,
                                          placeholder="选用抗病品种\n合理密植\n...")
        with col4:
            registered_str = st.text_input("登记药剂（逗号分隔）", value="", placeholder="苯醚甲环唑,吡唑醚菌酯")
            dosage = st.text_input("参考用量", value="", placeholder="25% 苯醚甲环唑 2000 倍液")
            timing = st.text_input("施药时期", value="", placeholder="发病初期喷施，7-10 天一次")
            interval = st.text_input("安全间隔期", value="", placeholder="21 天")

        submitted = st.form_submit_button("保存知识条目", type="primary", use_container_width=True)

    if submitted:
        entry = {
            "crop": crop.strip(),
            "disease": disease.strip(),
            "aliases": [a.strip() for a in aliases_str.split(",") if a.strip()],
            "symptoms": [s for s in symptoms_str.splitlines() if s.strip()],
            "occurrence_conditions": [c for c in conditions_str.splitlines() if c.strip()],
            "diagnosis_features": [f for f in features_str.splitlines() if f.strip()],
            "prevention": [p for p in prevention_str.splitlines() if p.strip()],
            "pesticide_reference": {
                "registered": [r.strip() for r in registered_str.split(",") if r.strip()],
                "dosage": dosage.strip(),
                "application_timing": timing.strip(),
                "safety_interval": interval.strip(),
            },
            "risk_level": risk_level,
        }

        ok, msg = save_disease(entry)
        if ok:
            st.success(msg)
        else:
            st.error(msg)


__all__ = ["render"]
