"""农技员端 · 农业知识中心管理。"""
from __future__ import annotations

import streamlit as st

from components import page_header, section_title, stat_card_html, risk_badge_html
from knowledge_center.loader import (
    load_diseases, load_pesticides, list_crops,
    save_disease, delete_disease,
)
from knowledge_center.registration import (
    RECOMMENDABLE, audit_all, load_registry, verify_product,
)


def _esc(text: object) -> str:
    """HTML 转义（登记库数据来自外部文件，不能直接拼进 HTML）。"""
    import html as _html
    return _html.escape(str(text if text is not None else ""))


def _registry_entry(name: str) -> dict:
    """取该药剂在合并登记库里的记录（含官方登记范围）。"""
    return load_registry().get(str(name or "")) or {}


def _is_registered_in_registry(name: str) -> bool:
    """该药剂在官方登记库里是否有登记范围声明。

    注意（重要更正）：不能凭 pesticide.json 的 notes 判断"未登记某作物"。
    实测「苯醚甲环唑」的人工 notes 写着"未登记玉米"，但官方登记库里它有
    玉米（还有小麦、大豆、高粱等 9 种作物）——人工 notes 是漏了行号的旧结论。
    这里一律以官方登记库为准。
    """
    prod = _registry_entry(name)
    return bool(prod.get("registered_crops") or prod.get("registered_targets"))


def _has_verified_dosage(prod: dict) -> bool:
    """该药剂是否有**已核验**的用量与安全间隔期。

    这两个字段只在人工核验条目里存在；官方公告附件不含它们。
    因此"有登记范围" ≠ "有权威剂量"，界面必须分别说明，否则会出现
    「参考用量（空） 安全间隔期（空）天」这种半截信息被误读。
    """
    return bool(str(prod.get("typical_dosage") or "").strip()) or \
        prod.get("safety_interval_days") not in (None, "")


def _fmt_interval(prod: dict) -> str:
    """安全间隔期的展示文本（缺失时不留空、更不显示无意义的天数）。"""
    days = prod.get("safety_interval_days")
    if days in (None, ""):
        return "未收录具体天数，请以登记标签为准"
    return f"{days} 天"


def _fmt_dosage(prod: dict) -> str:
    """参考用量的展示文本。"""
    dosage = str(prod.get("typical_dosage") or "").strip()
    return dosage if dosage else "未收录具体用量，请以登记标签为准"


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
    # 放在同一个 flex 行里（而非独立 st.columns），
    # 这样卡片会被拉伸到等高 —— 否则"覆盖作物"列出多个作物名换成多行，
    # 会把中间那张卡撑高，一行里出现高低不齐。
    # 注意区分两类农药数据，避免混淆：
    #   - 农药安全规范（pesticide.json）：人工逐条核验，含权威剂量与安全间隔期
    #   - 农药登记库（pesticide_registry.json）：官方公告批量导入，只含登记范围
    manual_products = sum(len(e.get("products") or []) for e in pesticides)
    registry_products = len(load_registry())

    cards_html = "".join([
        stat_card_html("病害知识条目", f"{len(diseases)}", "结构化病害条目", "#1F6B45"),
        stat_card_html("覆盖作物", f"{len(crops)}", "／".join(crops) if crops else "暂无", "#0d5c63"),
        stat_card_html("农药安全规范", f"{manual_products} 个", "人工核验·含权威剂量", "#1F6B45"),
        stat_card_html("农药登记库", f"{registry_products} 个", "官方公告·登记范围", "#0d5c63"),
    ])
    st.markdown(
        f'<div class="ag-cards">{cards_html}</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ======= 左侧 Tab 管理，右侧预览 =======
    tab_search, tab_pesticide, tab_registry, tab_add = st.tabs(
        ["知识检索", "农药安全规范", "农药登记库", "新增维护知识"]
    )

    with tab_search:
        _render_search_tab(diseases)

    with tab_pesticide:
        _render_pesticide_tab(pesticides)

    with tab_registry:
        _render_registry_tab()

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
                # 知识库 JSON 里的字段名是 favorable_conditions（有利发生条件），
                # 手动新增条目时用的键是 occurrence_conditions —— 两个都读，
                # 否则真实知识条目这一栏会显示为空（用户反馈的问题）。
                conds = (entry.get("favorable_conditions")
                         or entry.get("occurrence_conditions") or [])
                if isinstance(conds, str):
                    conds = [conds]
                if conds:
                    for c in conds:
                        st.markdown(f"- {c}")
                else:
                    st.caption("该条目未填写发生条件。")

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
    """农药安全规范：人工核验条目，明确标出"哪些字段已核验、哪些还没有"。

    卡片字段取值优先级（重要）：
      - 登记作物 / 防治对象：以**官方登记库**为准（人工条目常缺这几个字段，
        否则会出现「登记防治（空）」）
      - 参考用量 / 安全间隔期：只有人工核验条目才有；缺失时明确写
        "未收录，请以登记标签为准"，不留空标签、也不显示无意义的天数

    无登记范围声明的条目会被移入折叠区 —— 那属于审计材料。
    """
    section_title("农药类别与安全规范", "人工逐条核验 · 登记范围取自官方登记库")

    registered_entries: list[tuple[dict, dict]] = []
    unverified_entries: list[tuple[dict, dict]] = []
    forbidden_entries: list[dict] = []
    for entry in pesticides:
        if entry.get("category") == "禁限用农药提示":
            forbidden_entries.append(entry)
            continue
        for prod in entry.get("products") or []:
            bucket = registered_entries if _is_registered_in_registry(prod.get("name")) \
                else unverified_entries
            bucket.append((entry, prod))

    if not registered_entries:
        st.info("暂无可参考的已登记药剂条目。")

    by_cat: dict[str, list[dict]] = {}
    for entry, prod in registered_entries:
        by_cat.setdefault(str(entry.get("category") or "其他"), []).append(prod)

    for cat, prods in by_cat.items():
        st.markdown(f"##### {cat}")
        cards = []
        for prod in prods:
            name = str(prod.get("name") or "")
            reg = _registry_entry(name)

            # 登记作物/防治对象优先取官方登记库（人工条目常缺）
            crops = [str(c) for c in (reg.get("registered_crops") or [])]
            targets = [str(t) for t in (reg.get("registered_targets") or [])]
            crops_text = "、".join(crops) if crops else "—"
            targets_text = "、".join(targets[:8]) + ("…" if len(targets) > 8 else "") \
                if targets else "—"

            # 用量核验状态：明确区分"已核验"与"未收录"
            dosage_ok = _has_verified_dosage(prod)
            if dosage_ok:
                dosage_html = (
                    f'<div style="font-size:0.78rem;color:#546e7a;margin-top:0.2rem;">'
                    f'参考用量　{_esc(_fmt_dosage(prod))}</div>'
                    f'<div style="font-size:0.78rem;color:#546e7a;margin-top:0.2rem;">'
                    f'安全间隔期　{_esc(_fmt_interval(prod))}</div>'
                )
                badge = ('<span style="font-size:0.66rem;font-weight:700;color:#1F6B45;'
                         'background:#e8f1ec;border-radius:3px;padding:0.08rem 0.35rem;'
                         'margin-left:0.35rem;">剂量已核验</span>')
            else:
                dosage_html = (
                    '<div style="font-size:0.78rem;color:#b0bec5;margin-top:0.2rem;">'
                    '参考用量　本库未收录，请以农药登记标签为准</div>'
                )
                badge = ('<span style="font-size:0.66rem;font-weight:700;color:#b45309;'
                         'background:#fff3e0;border-radius:3px;padding:0.08rem 0.35rem;'
                         'margin-left:0.35rem;">剂量未收录</span>')

            basis = str(prod.get("registration_basis") or "").strip()
            if not basis and reg.get("reg_nos"):
                basis = "登记证号 " + "、".join(reg["reg_nos"][:3]) \
                    + ("…" if len(reg["reg_nos"]) > 3 else "")
            basis_html = (
                f'<div style="font-size:0.73rem;color:#90a4ae;margin-top:0.25rem;">'
                f'登记依据　{_esc(basis)}</div>' if basis else ""
            )
            mode = str(prod.get("mode") or "").strip()
            mode_html = (
                f'<div style="font-size:0.78rem;color:#78909c;margin-top:0.25rem;">'
                f'作用机制　{_esc(mode)}</div>' if mode else ""
            )

            cards.append(
                f'<div class="ag-card" style="padding:0.7rem 0.9rem;margin-bottom:0.5rem;">'
                f'<div style="font-weight:600;color:#0d5c63;font-size:0.95rem;">'
                f'{_esc(name)}{badge}</div>'
                f'{mode_html}'
                f'<div style="font-size:0.78rem;color:#546e7a;margin-top:0.2rem;">'
                f'登记作物　{_esc(crops_text)}</div>'
                f'<div style="font-size:0.78rem;color:#546e7a;margin-top:0.2rem;">'
                f'登记防治　{_esc(targets_text)}</div>'
                f'{dosage_html}'
                f'{basis_html}'
                f'</div>'
            )
        st.markdown("".join(cards), unsafe_allow_html=True)

    # ---- 无登记范围声明的条目（审计材料，默认折叠）----
    if unverified_entries:
        st.divider()
        with st.expander(
            f"⚠ 未见登记范围声明（{len(unverified_entries)} 项）—— 仅供核查",
            expanded=False,
        ):
            st.caption(
                "这些药剂在官方登记库中**查不到登记作物与防治对象**，无法确认能否使用。"
                "保留在此仅为追溯历史标注，**不应作为推荐或用药依据**。"
            )
            for entry, prod in unverified_entries:
                st.markdown(
                    f'<div style="border-left:3px solid #e67e22;background:#fff8f0;'
                    f'border-radius:4px;padding:0.55rem 0.75rem;margin-bottom:0.45rem;">'
                    f'<div style="font-weight:600;color:#b45309;">'
                    f'{_esc(prod.get("name", ""))}</div>'
                    f'<div style="font-size:0.76rem;color:#8d6e63;margin-top:0.15rem;">'
                    f'分类　{_esc(entry.get("category") or "—")}　'
                    f'历史标注用量　{_esc(prod.get("typical_dosage") or "无")}</div>'
                    f'<div style="font-size:0.75rem;color:#a1887f;margin-top:0.2rem;'
                    f'line-height:1.5;">说明　'
                    f'{_esc(str(prod.get("notes") or "无说明")[:160])}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ---- 禁限用提示 ----
    for entry in forbidden_entries:
        st.divider()
        st.markdown("##### 国家禁限用农药提示")
        forbidden = entry.get("forbidden_substances", []) or []
        cols = st.columns(min(3, len(forbidden)) or 1)
        for i, f in enumerate(forbidden):
            with cols[i % len(cols)]:
                st.markdown(
                    f'<div style="border-left:3px solid #c0392b;padding:0.4rem 0.7rem;'
                    f'background:#ffebee;border-radius:4px;margin-bottom:0.4rem;">'
                    f'<div style="font-weight:600;color:#c0392b;">{_esc(f.get("name", ""))}</div>'
                    f'<div style="font-size:0.78rem;color:#78909c;margin-top:0.2rem;">'
                    f'{_esc(f.get("status", ""))}</div>'
                    f'<div style="font-size:0.75rem;color:#b0bec5;margin-top:0.15rem;">'
                    f'{_esc(f.get("reason", ""))}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("##### 安全使用原则")
        for p in entry.get("safety_principles", []) or []:
            st.markdown(f"- {p}")


# =========================================================================
# Tab 3: 农药登记库（官方公告批量导入）
# =========================================================================

# 判定状态的中文短标签（表格里用）
_STATUS_SHORT = {
    "registered": "✅ 已登记本作物+本防治对象",
    "registered_crop_only": "⚠ 本作物已登记·防治对象不同",
    "out_of_scope": "⛔ 超范围·未登记本作物",
    "unregistered": "⛔ 未登记本作物",
    "unverified": "❔ 登记库未收录",
    "mixture": "◇ 复配剂·须核对配比",
    "unknown": "· 名称缺失",
}


def _registry_options() -> tuple[list[str], list[str]]:
    """返回 (全部登记作物, 全部防治对象) 供筛选下拉。"""
    crops: set[str] = set()
    targets: set[str] = set()
    for prod in load_registry().values():
        crops.update(str(c) for c in (prod.get("registered_crops") or []) if c)
        targets.update(str(t) for t in (prod.get("registered_targets") or []) if t)
    return sorted(crops), sorted(targets)


def _render_registry_tab() -> None:
    """农药登记库：可搜索、可筛选，是核对数据准确性的入口。

    数据来源：农业农村部农药管理司《农药登记信息》公告附件（官方 XLS）。
    采集脚本见 tools/harvest_registration.py。
    """
    section_title("农药登记库", "官方登记数据 · 按名称/作物/防治对象筛选")

    registry = load_registry()
    if not registry:
        st.warning(
            "登记库为空。请运行 `python tools/harvest_registration.py --import` "
            "采集官方登记数据后重试。"
        )
        return

    reg_nos: set[str] = set()
    crop_places: set[str] = set()
    for prod in registry.values():
        for n in (prod.get("reg_nos") or ([prod.get("reg_no")] if prod.get("reg_no") else [])):
            if n:
                reg_nos.add(str(n))
        if prod.get("crop_place"):
            crop_places.add(str(prod["crop_place"]))

    # ---- 数据概况 ----
    st.markdown(
        "　".join([
            f"**产品 {len(registry)}** 个",
            f"**登记作物/场所 {len(crop_places)}** 种",
            f"**登记证号 {len(reg_nos)}** 个",
        ])
    )
    st.caption(
        "来源：农业农村部农药管理司《农药登记信息》公告附件（2022 起，去重后 12000+ 登记证号）。"
        "公告只覆盖登记的新增/延续/变更，因此更早登记且此后未延续的品种可能查不到。"
        "**本库不含用药量与安全间隔期**——这两项只在农药登记标签上，请以标签为准。"
    )

    # ---- 筛选 ----
    all_crops, all_targets = _registry_options()
    f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1])
    with f1:
        name_kw = st.text_input(
            "农药名称", value="", placeholder="如 苯醚甲环唑 / 三唑酮",
            key="reg_name_kw",
        )
    with f2:
        crop_sel = st.selectbox("登记作物", ["全部"] + all_crops, key="reg_crop_sel")
    with f3:
        target_kw = st.text_input(
            "防治对象", value="", placeholder="如 锈病 / 蚜虫", key="reg_target_kw",
        )
    with f4:
        status_sel = st.selectbox(
            "核验结论",
            ["全部", "✅ 已登记本作物+本防治对象", "⚠ 本作物已登记·防治对象不同",
             "⛔ 未登记本作物", "❔ 登记库未收录", "◇ 复配剂·须核对配比"],
            key="reg_status_sel",
        )

    # ---- 过滤 ----
    rows: list[dict] = []
    for name, prod in registry.items():
        crops_ = [str(c) for c in (prod.get("registered_crops") or [])]
        targets_ = [str(t) for t in (prod.get("registered_targets") or [])]

        if name_kw.strip() and name_kw.strip() not in name:
            continue
        if crop_sel != "全部" and crop_sel not in crops_:
            continue
        if target_kw.strip() and not any(target_kw.strip() in t for t in targets_):
            continue

        # 核验结论：取该产品第一个登记作物 + 第一个防治对象作为代表组合，
        # 与表格展示的两列一致，避免出现"列里写着某作物、结论却针对另一个作物"。
        rep_crop = crop_sel if crop_sel != "全部" else (crops_[0] if crops_ else "")
        rep_target = targets_[0] if targets_ else ""
        status = verify_product(name, rep_crop, rep_target)["status"]

        if status_sel != "全部" and _STATUS_SHORT.get(status, status) != status_sel:
            continue

        rows.append({
            "农药名称": name,
            "登记作物/场所": prod.get("crop_place") or "、".join(crops_) or "—",
            "防治对象": "、".join(targets_[:4]) + ("…" if len(targets_) > 4 else ""),
            "剂型": prod.get("formulation") or "—",
            "毒性": prod.get("toxicity") or "—",
            "类别": prod.get("category") or "—",
            "登记证号": (prod.get("reg_nos") or [prod.get("reg_no")])[0] or "—",
            "核验结论": _STATUS_SHORT.get(status, status),
        })

    # ---- 结果 ----
    st.divider()

    if not rows:
        st.info("无匹配产品。可放宽筛选条件，或该品种确实不在登记库中。")
    else:
        cap = 300
        shown = rows[:cap]

        # ---- 明细表（列宽受控，减少横向滚动）----
        st.caption(f"共 {len(rows)} 条，下表显示前 {min(cap, len(rows))} 条；用上方筛选缩小范围。")
        st.dataframe(
            shown,
            hide_index=True,
            height=420,
            column_config={
                "农药名称": st.column_config.TextColumn(width="medium"),
                "登记作物/场所": st.column_config.TextColumn(width="medium"),
                "防治对象": st.column_config.TextColumn(width="medium"),
                "剂型": st.column_config.TextColumn(width="small"),
                "毒性": st.column_config.TextColumn(width="small"),
                "类别": st.column_config.TextColumn("类别", width="small"),
                "登记证号": st.column_config.TextColumn(width="small"),
                "核验结论": st.column_config.TextColumn(width="medium"),
            },
        )
        if len(rows) > cap:
            st.caption(f"⚠ 结果较多，另有 {len(rows) - cap} 条未显示，建议加筛选条件。")

        # ---- 单产品详情：命中很少时直接展开，省去翻表 ----
        if len(rows) <= 12:
            with st.expander(f"展开看这 {len(rows)} 条的完整登记信息", expanded=False):
                for r in shown:
                    with st.expander(f"{r['农药名称']}　{r['核验结论']}", expanded=False):
                        st.markdown(
                            f"登记证号　{r['登记证号']}\n\n"
                            f"登记作物/场所　{r['登记作物/场所']}\n\n"
                            f"防治对象　{r['防治对象']}\n\n"
                            f"剂型　{r['剂型']}　毒性　{r['毒性']}　类别　{r['类别']}"
                        )

    # ---- 全库审计：找出病害条目标注却未登记本作物的药剂 ----
    st.divider()
    section_title("登记合规审计", "检查病害条目标注的药剂是否真的登记在本作物上")
    st.caption(
        "`data/*.json` 里的 `registered` / `chemical_control` 是历史资料，未经过登记核验。"
        "点击下方按钮可列出所有冲突项，是核对数据质量的入口。"
    )
    if st.button("运行全库审计", key="reg_audit_btn"):
        audit_rows = audit_all()
        blocked = [r for r in audit_rows if r["blocked"]]
        if not blocked:
            st.success("未发现冲突：所有标注药剂均通过登记核验。")
        else:
            st.warning(f"发现 {len(blocked)} 条病害条目存在超范围用药标注：")
            for r in blocked:
                reasons = []
                for p in r["products"]:
                    if p["status"] in ("out_of_scope", "unregistered"):
                        reasons.append(f"**{p['product']}**：{p.get('reason', '')}")
                if reasons:
                    with st.expander(f"{r['crop']} · {r['disease']}（{len(reasons)} 项）"):
                        for line in reasons:
                            st.markdown(f"- {line}")

        summary = {
            "已核验可通过": sum(len(r["registered"]) for r in audit_rows),
            "禁止推荐": sum(len(r["blocked"]) for r in audit_rows),
            "需核对标签": sum(len(r["needs_review"]) for r in audit_rows),
        }
        st.markdown(
            "　".join(f"**{k} {v}** 项" for k, v in summary.items())
            + f"　（共 {len(audit_rows)} 条病害条目）"
        )


# =========================================================================
# Tab 4: 新增 / 维护
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
