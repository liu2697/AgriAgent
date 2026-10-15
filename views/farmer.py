"""农户端 · 农智链 AgriAgent — 作物病虫害智能诊断采集（移动端优先）。"""
from __future__ import annotations

import html
import io
import re

import streamlit as st
from PIL import Image

from config import CROPS, SOIL_TYPES, GROWTH_STAGES, APP_NAME, APP_SUBTITLE
from agent import AgriAgent, AgentStep
from memory import history as memory
from components import risk_badge_html
from components.symptom_chips import CHIP_LABELS, build_symptom_text
from components.layout import fmt_cn_time, flow_steps_html, task_status_display

# 智能体执行流程步骤名称（面向用户的统一表达）
_FLOW_LABELS = {
    "retrieve_knowledge": "知识检索",
    "vision_analyze": "图像识别",
    "query_history": "历史记录",
    "llm_diagnose": "方案生成",
    "safety_review": "风险评估",
    "save_record": "记录归档",
}


def render() -> None:
    _render_header()

    # ==================== 上传 / 拍照（共用一个框） ====================
    image_bytes = _render_image_input()

    # ==================== 作物与地块信息 ====================
    st.markdown("##### 作物与地块信息")
    crop = st.selectbox("作物类型", CROPS, index=0, key="u_crop")

    # 选「其他」时让农户填写具体作物名，并解析为规范作物。
    # 背景：农户写的是俗称（土豆/苞米/谷子/莜麦…），若直接拿原文检索作物，
    # 会因为与知识库的规范作物名不一致而检索不到任何条目。
    crop_query = crop
    if crop == "其他":
        other_crop = st.text_input(
            "请填写具体作物名称",
            value=st.session_state.get("u_other_crop", ""),
            placeholder="如 谷子 / 土豆 / 莜麦 / 苦荞（写俗称也能识别）",
            key="u_other_crop",
        ).strip()
        if other_crop:
            from knowledge_center.crop_aliases import resolve_crop
            resolved = resolve_crop(other_crop)
            if resolved:
                crop_query = resolved
                st.caption(f"已识别为：**{resolved}**，将按「{resolved}」的知识库条目诊断。")
            else:
                crop_query = other_crop
                st.warning(
                    f"「{other_crop}」暂未收录进知识库，本次将按通用植保知识诊断，"
                    "结论可能不够具体，建议提交农技员复核。"
                )

    growth_stage = st.selectbox("生长阶段", GROWTH_STAGES, index=2, key="u_stage")

    col_a, col_b = st.columns(2)
    with col_a:
        soil_type = st.selectbox("土壤类型", SOIL_TYPES, index=0, key="u_soil")
        area = st.number_input("面积（亩）", min_value=0.1, max_value=10000.0, value=5.0, step=0.1, key="u_area")
    with col_b:
        location = st.text_input("地理位置", value="", placeholder="如 河北石家庄", key="u_loc")
        symptoms_input = st.text_area(
            "异常现象描述（可选）",
            value="", height=72,
            placeholder="可直接输入，也可点下方常用词快速填写…",
            key="u_symptoms",
        )
        _render_symptom_quick_picks()

    # 症状文本 = 输入框内容 + 点选的常用词
    symptoms = _compose_symptoms(symptoms_input)

    farmer_name = st.text_input("姓名（可选）", value=st.session_state.get("farmer_name", ""), key="u_name")
    if farmer_name:
        st.session_state["farmer_name"] = farmer_name
    contact = st.text_input("联系方式（可选）", value=st.session_state.get("farmer_contact", ""), key="u_contact")
    if contact:
        st.session_state["farmer_contact"] = contact

    # ==================== 开始诊断 ====================
    st.markdown("<div style='height:0.35rem'></div>", unsafe_allow_html=True)
    diagnose_clicked = st.button("开始智能诊断", type="primary", use_container_width=True, key="u_diag")

    if diagnose_clicked:
        progress = st.status("正在诊断，请稍候…", expanded=True)

        def _on_step(step: AgentStep) -> None:
            icon_map = {"done": "✓", "running": "→", "failed": "✗", "skipped": "⊘", "pending": "·"}
            progress.write(
                f"{icon_map.get(step.status, '·')}  {step.label}"
                + (f"　{step.detail}" if step.detail else "")
            )

        agent = AgriAgent(on_step=_on_step)
        # 页面侧兜底：Agent 内部异常不再以红色堆栈暴露给农户，统一转诚实失败视图
        try:
            result = agent.run(
                # 用解析后的规范作物名（crop_query）检索与诊断：
                # 农户选「其他」并填俗称（如"土豆"）时，这里已解析为「马铃薯」，
                # 否则作物硬过滤会因名称不一致而检索不到条目。
                image_bytes=image_bytes, crop=crop_query, growth_stage=growth_stage,
                soil_type=soil_type, area=area, location=location,
                symptoms=symptoms, enable_memory=True,
            )
        except Exception as exc:
            result = {
                "success": False,
                "error": f"诊断执行异常：{exc}",
                "content": "",
                "plan": [],
            }

        diag_ok = result.get("success") is not False
        progress.update(
            label="诊断完成" if diag_ok else "诊断未完成",
            state="complete" if diag_ok else "error",
            expanded=False if diag_ok else True,
        )

        # 结果持久化到会话：后续点击“下载 / 提交工单 / 重新诊断”的轮次仍能渲染结果区
        # 注意 crop 存"农户原始选择/填写"，crop_resolved 存解析后的规范作物名：
        # 报告与地块档案展示原文更直观，检索与归档用规范名更可靠。
        st.session_state["farmer_result"] = {
            "result": result,
            "crop": crop,
            "crop_resolved": crop_query,
            "growth_stage": growth_stage,
            "soil_type": soil_type,
            "area": area,
            "location": location,
            "symptoms": symptoms,
            "risk_level": (
                (result.get("review") or {}).get("risk_level", "无")
                if diag_ok else "未完成"
            ),
            "image_ext": _guess_ext(image_bytes),
        }
        st.rerun()
    else:
        st.caption("清晰的病斑特写和准确的地块信息，有助于获得更准确的诊断结果。")

    # ---- 从会话渲染诊断结果（保证提交按钮在点击轮次可见可点） ----
    saved = st.session_state.get("farmer_result")
    if saved:
        _render_result(
            saved["result"],
            crop=saved["crop"], growth_stage=saved["growth_stage"],
            area=saved["area"], soil_type=saved["soil_type"],
            location=saved["location"], symptoms=saved["symptoms"],
            risk_level=saved["risk_level"], image_bytes=image_bytes,
            image_ext=saved["image_ext"],
        )

    # ==================== 我的历史诊断（P1-2 · 只读） ====================
    _render_my_history()

    # ==================== 审核进度查询 ====================
    st.markdown("---")
    st.markdown("##### 审核进度查询")
    col_q1, col_q2 = st.columns([3, 1])
    query = col_q1.text_input(
        "工单编号", value="",
        placeholder="如 TK-1EE42B",
        key="farmer_query_input",
    )
    if col_q2.button("查询", use_container_width=True, key="farmer_query_btn"):
        task = _find_task_by_short(query)
        if task:
            st.session_state["farmer_query_task"] = task["task_id"]
        else:
            st.session_state["farmer_query_task"] = None
            st.error("未找到该工单，请核对编号")

    tid = (
        st.session_state.get("farmer_query_task")
        or st.session_state.get("farmer_last_task")
    )
    if tid:
        _render_task_status_card(tid)


# =========================================================================
# 顶部品牌区
# =========================================================================

def _render_header() -> None:
    """农户端品牌区。

    按用户要求移除了「建档地块 / 历史诊断 / 覆盖作物」三个统计框：
    这些数字对农户本人没有指导意义，反而会把首屏空间从"拍照片、填信息"
    这件正事上引开。同时也少了对历史统计与统计服务的两次查询。
    """
    st.markdown(
        f"""
        <div class="ag-m-hero">
            <div class="ag-m-hero-badge">农户端 · 智能生产管理</div>
            <div class="ag-m-hero-title">{APP_NAME}</div>
            <div class="ag-m-hero-sub">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================================
# 诊断结果
# =========================================================================

def _render_safety_issues(issues: list, warnings: list) -> None:
    """P1-3：醒目展示安全审核问题明细与通用提醒（仅读取 review 字段）。"""
    level_map = {"high": "高", "medium": "中", "low": "低"}
    color_map = {"高": "#d32f2f", "中": "#ef6c00", "低": "#f9a825"}
    rows = []
    for iss in issues:
        if not isinstance(iss, dict):
            continue
        lvl = level_map.get(str(iss.get("level", "")), "·")
        color = color_map.get(lvl, "#607d8b")
        evidence = str(iss.get("evidence") or "").strip()
        ev_html = (
            f'<div style="font-size:0.78rem;color:#78909c;margin-top:0.15rem;">'
            f'依据：{html.escape(evidence)}</div>'
            if evidence else ""
        )
        rows.append(
            '<div style="display:flex;gap:0.6rem;align-items:flex-start;'
            'padding:0.4rem 0.2rem;border-bottom:1px dashed #eceff1;">'
            f'<div style="min-width:3.6em;font-weight:700;color:{color};">{lvl}风险</div>'
            '<div><div style="font-weight:600;">'
            f'【{html.escape(str(iss.get("category", "")))}】'
            f'{html.escape(str(iss.get("message", "")))}</div>'
            f'{ev_html}</div></div>'
        )
    if rows:
        st.markdown(
            '<div class="ag-rpt-section"><div class="ag-rpt-sec-head">'
            '<span class="ag-rpt-sec-bar"></span>'
            '<span class="ag-rpt-sec-title">安全风险明细</span></div>'
            + "".join(rows) + "</div>",
            unsafe_allow_html=True,
        )
    if warnings:
        st.info("通用安全提醒：" + "；".join(str(w) for w in warnings))


def _render_safety_record(result: dict) -> None:
    """P1-3：完整安全审核记录（证据留存，纯读取，不调用任何服务）。"""
    with st.expander("查看完整安全审核记录", expanded=False):
        st.markdown(result.get("review_summary") or "（无审核摘要记录）")


def _render_result(result, *, crop, growth_stage, area, soil_type, location,
                   symptoms, risk_level, image_bytes, image_ext) -> None:
    # P1-1：失败必须诚实展示，禁止继续渲染“成功报告”伪装诊断结论
    if result.get("success") is False:
        _render_failed_result(result)
        return

    success = result.get("success", True)
    kb = result.get("knowledge", [])
    content = result.get("content", "")
    plan_steps = result.get("plan", [])
    top1 = kb[0]["disease"] if kb else "综合诊断见报告内容"

    # ---- P1-3：Safety 安全闸门（只读 result["review"]，不改 Agent 数据结构）----
    review = result.get("review") or {}
    review_issues = review.get("issues", []) or []
    review_warnings = review.get("warnings", []) or []
    review_risk = review.get("risk_level") or risk_level or "未知"
    review_safe = review.get("safe")
    safety_unknown = review_risk == "未知"
    safety_blocked = (review_safe is False) or (
        review_safe is None and not safety_unknown and review_risk == "高"
    )

    if safety_blocked:
        st.error("⚠ 安全审核未通过：以下处置建议存在安全风险，禁止直接采纳。")
    elif safety_unknown:
        st.warning("⚠ 安全审核状态未知：本次安全审核未正常完成，请勿直接采纳处置建议。")

    # ---- 未配置密钥时必须显著提示（避免示例内容被误认为大模型输出）----
    _src_txt = str(result.get("source", ""))
    if "示例模式" in _src_txt or "mock" in _src_txt.lower():
        st.warning(
            "⚠️ 当前未配置 AI 服务密钥，本报告为**内置示例诊断**（仅用于功能演示），"
            "并非大模型结合本块地数据的真实诊断结论；配置密钥后即为真实模型输出。"
        )

    # ---- 报告头 ----
    st.markdown(
        f"""
        <div class="ag-rpt-header">
            <span class="ag-rpt-hd-badge">智能植保诊断报告</span>
            <div class="ag-rpt-hd-title">{APP_NAME}</div>
            <div class="ag-rpt-hd-sub">{APP_SUBTITLE}</div>
            <div class="ag-rpt-hd-tags">
                <span class="ag-rpt-hd-tag">作物　{crop}</span>
                <span class="ag-rpt-hd-tag">阶段　{growth_stage}</span>
                <span class="ag-rpt-hd-tag">面积　{area}亩</span>
                <span class="ag-rpt-hd-tag">风险等级　{risk_level}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- 病害判断 + 风险等级 ----
    st.markdown(
        f"""
        <div class="ag-rpt-section">
            <div class="ag-rpt-sec-head">
                <span class="ag-rpt-sec-bar"></span>
                <span class="ag-rpt-sec-title">病害判断</span>
            </div>
            <div class="ag-rpt-identify">
                <div class="ag-rpt-id-field">
                    <div class="ag-rpt-id-lbl">判断结果</div>
                    <div class="ag-rpt-id-val ok">{top1}</div>
                </div>
                <div class="ag-rpt-id-field">
                    <div class="ag-rpt-id-lbl">综合风险等级</div>
                    <div class="ag-rpt-id-val">{risk_level} {risk_badge_html(risk_level)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- P1-3：安全风险明细（高风险/审核未知时在醒目位置展示，不放折叠区）----
    if safety_blocked or safety_unknown:
        _render_safety_issues(review_issues, review_warnings)

    # ---- 处理建议 ----
    if safety_blocked:
        # P1-3：未通过安全审核的原始建议——保留原文但放入明确的风险容器，禁止当作正常建议采纳
        st.markdown(
            f"""
            <div class="ag-rpt-section">
                <div class="ag-rpt-sec-head">
                    <span class="ag-rpt-sec-bar"></span>
                    <span class="ag-rpt-sec-title">⚠ 未通过安全审核的原始建议（禁止直接采纳）</span>
                </div>
                <div style="border:2px solid #d32f2f;border-radius:12px;background:#fff5f5;padding:0.7rem 0.5rem;margin-top:0.4rem;">
                    <div style="color:#d32f2f;font-weight:700;margin:0 0.2rem 0.5rem;">
                        ⛔ 以下为 AI 原始建议，未通过安全审核，仅作风险追踪证据，禁止作为处置依据直接采纳。
                    </div>
                    <div class="ag-rpt-advice">
                        {_advice_block('ag-rpt-current', '原始防治方案（未通过审核）',
                                       _extract_section(content, '防治') or '请参考报告正文中的防治建议。')}
                        {_advice_block('ag-rpt-farm', '原始农事管理建议（未通过审核）',
                                       _extract_section(content, '农事') or _extract_section(content, '管理') or '结合本地气候与作物生长阶段，科学灌溉、合理施肥、定期巡田。')}
                        {_advice_block('ag-rpt-risk-block', '原始风险提示（未通过审核）',
                                       _extract_section(content, '风险') or _extract_section(content, '注意') or '用药前请仔细阅读农药标签，严格按照推荐剂量和安全间隔期操作；如病情持续加重，请及时咨询当地农技人员。')}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="ag-rpt-section">
                <div class="ag-rpt-sec-head">
                    <span class="ag-rpt-sec-bar"></span>
                    <span class="ag-rpt-sec-title">处理建议</span>
                </div>
                <div class="ag-rpt-advice">
                    {_advice_block('ag-rpt-current', '防治方案',
                                   _extract_section(content, '防治') or '请参考报告正文中的防治建议。')}
                    {_advice_block('ag-rpt-farm', '农事管理建议',
                                   _extract_section(content, '农事') or _extract_section(content, '管理') or '结合本地气候与作物生长阶段，科学灌溉、合理施肥、定期巡田。')}
                    {_advice_block('ag-rpt-risk-block', '风险提示',
                                   _extract_section(content, '风险') or _extract_section(content, '注意') or '用药前请仔细阅读农药标签，严格按照推荐剂量和安全间隔期操作；如病情持续加重，请及时咨询当地农技人员。')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---- 配药计算器（把"亩用量"换算成"我这块地要买多少药、兑多少水"）----
    _render_dosage_calculator(kb, area)

    # ---- 农药登记核验（只展示权威登记数据确认可用的药剂）----
    _render_registration_card(result.get("registration") or {})

    # ---- 智能体执行流程 ----
    _render_analysis_flow(plan_steps)

    # ---- 诊断依据 ----
    _render_knowledge_basis(kb)

    # ---- 可信度评分 ----
    _render_confidence_card(result, crop, growth_stage, location, symptoms)

    # ---- 完整报告正文（去 Markdown 标记 · 正式报告形式）----
    with st.expander("查看完整诊断报告", expanded=False):
        if success:
            from components.markdown_helper import plain_report_html
            st.markdown(plain_report_html(content), unsafe_allow_html=True)
        else:
            st.error(content or "诊断失败")

    # ---- P1-3：完整安全审核记录（证据留存）----
    if safety_blocked or safety_unknown:
        _render_safety_record(result)

    # ---- 安全提示 ----
    st.markdown(
        """
        <div class="ag-rpt-disclaimer">
            本报告由系统智能生成，仅供辅助决策参考。实际防治请结合田间实况，并咨询当地农技推广人员；
            用药须遵守农药标签要求与安全间隔期，严禁使用国家明令禁止的农药。
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- 操作按钮 ----
    b1, b2 = st.columns(2)
    with b1:
        st.download_button(
            "下载诊断报告",
            data=content.encode("utf-8"),
            file_name=f"农智链AgriAgent_{crop}_{area}亩.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with b2:
        if st.button("提交农技员审核", use_container_width=True, key="rpt_submit"):
            _submit_task(
                image_bytes=image_bytes, image_ext=image_ext,
                crop=crop, growth_stage=growth_stage,
                soil_type=soil_type, area=area,
                location=location, symptoms=symptoms,
                ai_result={**result, "risk_level": risk_level},
            )
    st.caption("诊断完成后请点击「提交农技员审核」，工单才会进入农技员端处理。")
    if st.button("重新诊断", use_container_width=True, key="rpt_rerun"):
        st.session_state.pop("farmer_result", None)
        st.rerun()


# =========================================================================
# 诊断失败视图（诚实展示失败，不伪装成功，不编造 fallback 诊断）
# =========================================================================

def _failure_reason(result: dict) -> str:
    """提取真实失败原因：error/message → plan 中 failed 步骤 → content 失败描述。"""
    reason = str(result.get("error") or result.get("message") or "").strip()
    if reason:
        return reason[:300]
    for s in (result.get("plan") or []):
        if s.get("status") == "failed" and s.get("detail"):
            return str(s["detail"])[:300]
    m = re.search(r"LLM 调用失败[：:].*", str(result.get("content") or ""))
    if m:
        return m.group(0)[:300]
    return ""


def _render_failed_result(result: dict) -> None:
    """success=False 专用视图：错误状态 + 真实原因 + failed 步骤 + 重试入口。

    不渲染：诊断结论、病名判断、处理建议、正常风险等级、成功报告卡片。
    """
    st.error("智能诊断未完成：本次未能生成有效诊断报告，以下内容不是诊断结论。")

    reason = _failure_reason(result)
    if reason:
        st.warning(f"失败原因：{reason}")

    plan_steps = result.get("plan", []) or []
    if plan_steps:
        _render_analysis_flow(plan_steps)

    with st.expander("查看错误详情", expanded=False):
        rows = []
        for s in plan_steps:
            if s.get("status") == "failed" and s.get("detail"):
                label = _FLOW_LABELS.get(s.get("name", ""), s.get("label", ""))
                rows.append(f"- {label}：{s['detail']}")
        if rows:
            st.markdown("\n".join(rows))
        else:
            st.caption("无更多错误详情。")

    st.info("请检查网络连接与模型服务状态后，重新上传图片并点击「开始智能诊断」。")

    # 重新诊断：清除本次失败结果回到采集表单，复用现有真实提交链路（无新建诊断逻辑）
    if st.button("重新诊断", type="primary", use_container_width=True, key="failed_rerun"):
        st.session_state.pop("farmer_result", None)
        st.rerun()


# =========================================================================
# 我的历史诊断（P1-2 · 纯只读，不调用 Agent / LLM / RAG）
# =========================================================================

def _history_empty_hint() -> None:
    st.info("暂无历史诊断记录")
    st.caption("完成一次智能诊断后，诊断结果会自动保存在这里。")


def _register_my_plot_from_session() -> None:
    """从本会话已完成的成功诊断中登记当前农户的地块（纯会话记录）。

    只读取 session_state.farmer_result，不修改诊断写入链路；
    失败诊断（success=False）不会产生 diagnosis_record，因此不登记。
    location 为空时不登记：空位置会落入共享的“未命名地块”，
    保守起见不作为“我的地块”展示（隐私优先）。
    """
    saved = st.session_state.get("farmer_result")
    if not saved:
        return
    result = saved.get("result") or {}
    if result.get("success") is False:
        return
    location = str(saved.get("location") or "").strip()
    crop = str(saved.get("crop") or "").strip()
    area = saved.get("area")
    if not location or not crop or area in (None, ""):
        return
    try:
        area = round(float(area), 1)
    except (TypeError, ValueError):
        return
    mine = st.session_state.get("farmer_my_plots") or []
    if not any(
        p.get("location") == location and p.get("crop") == crop
        and p.get("area") == area
        for p in mine
    ):
        st.session_state["farmer_my_plots"] = mine + [
            {"location": location, "crop": crop, "area": area}
        ]


def _collect_my_records(my_plots: list[dict], limit: int = 5) -> list[dict]:
    """按当前农户会话登记的地块逐一读取历史诊断（plot_key 精确匹配）。

    过滤依据（重要）：diagnosis_records 以 plot_key（位置::作物::面积亩）
    作为地块唯一身份，记录本身不含 farmer_id；农户端可可靠确定的归属
    只有“本会话亲自完成过成功诊断的地块”。因此：
      - 仅查询这些地块（memory.get_history → plot_key 精确匹配）；
      - 绝不全量拉取 diagnosis_records；
      - 绝不展示其他农户 / 未登记地块的记录。
    """
    merged: list[dict] = []
    for p in my_plots[-10:]:  # 会话内地块数量上限保护
        merged.extend(memory.get_history(
            p["location"], p["crop"], p["area"], limit=limit
        ))
    merged.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return merged[:limit]


def _render_history_detail(rec: dict) -> None:
    """单条历史记录详情：纯读取数据库已存字段，不做任何二次调用。"""
    risk = rec.get("risk_level") or "未知"
    # P1-3：历史高风险记录必须明确提示未通过安全审核（仅读取已存 risk_level）
    if risk == "高":
        st.warning("⚠ 此诊断未通过安全审核：历史记录中的相关处置建议仅作为风险追踪信息，不应直接采纳。")
    st.markdown(f"**诊断时间**　{fmt_cn_time(str(rec.get('timestamp') or ''))}")
    st.markdown(
        f"**地块信息**　{rec.get('location', '')} · {rec.get('crop', '')}"
        f" · {rec.get('growth_stage', '')} · {rec.get('area', '')}亩"
    )
    st.markdown(f"**风险等级**　{risk} {risk_badge_html(risk)}")
    st.markdown("**诊断结论/摘要**")
    st.markdown(rec.get("diagnosis_summary") or "（记录中无诊断摘要）")
    st.markdown("**处理建议**")
    st.markdown(rec.get("recommendation_summary") or "（记录中无处理建议）")


def _render_my_history() -> None:
    """农户端“我的历史诊断”只读区域（P1-2）。

    - 数据范围：仅当前会话中当前农户完成过成功诊断的地块（见 _collect_my_records）
    - 详情为纯读取（diagnosis_summary / recommendation_summary / risk_level 等已存字段）
    - 读取失败时如实提示，不伪造空数据
    """
    _register_my_plot_from_session()
    my_plots = st.session_state.get("farmer_my_plots") or []

    st.markdown("##### 我的历史诊断")

    if not my_plots:
        _history_empty_hint()
        return

    try:
        records = _collect_my_records(my_plots, limit=5)
    except Exception as exc:  # 数据层异常：如实提示，不伪造空数据
        st.warning(f"历史诊断读取失败：{exc}")
        return

    if not records:
        _history_empty_hint()
        return

    for rec in records:
        ts = fmt_cn_time(str(rec.get("timestamp") or ""))
        risk = rec.get("risk_level") or "未知"
        summary = _clean_markdown(str(rec.get("diagnosis_summary") or ""))
        preview = summary.splitlines()[0][:40] if summary else ""
        st.markdown(
            f"""
            <div class="ag-rpt-section">
                <div class="ag-rpt-sec-head">
                    <span class="ag-rpt-sec-bar"></span>
                    <span class="ag-rpt-sec-title">{html.escape(ts)}</span>
                </div>
                <div class="ag-flow-line done">
                    <span class="ag-flow-mark">✓</span>
                    <span class="ag-flow-name">{html.escape(str(rec.get('location') or ''))} · {html.escape(str(rec.get('crop') or ''))} · {rec.get('area', '')}亩</span>
                </div>
                <div style="font-size:0.78rem;color:#546e7a;padding:0 0.2rem 0.45rem 1.75rem;">
                    {html.escape(preview)}　{risk_badge_html(risk)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("查看诊断详情"):
            _render_history_detail(rec)


# =========================================================================
# 分析流程（简单状态勾选，不做机器人效果）
# =========================================================================

def _render_analysis_flow(plan_steps: list[dict]) -> None:
    if not plan_steps:
        return
    rows = []
    for s in plan_steps:
        status = s.get("status", "pending")
        mark = {"done": "✓", "skipped": "—", "failed": "✗"}.get(status, "·")
        cls = {"done": "done", "skipped": "skip", "failed": "fail"}.get(status, "")
        label = _FLOW_LABELS.get(s.get("name", ""), s.get("label", ""))
        rows.append(
            f'<div class="ag-flow-line {cls}">'
            f'<span class="ag-flow-mark">{mark}</span>'
            f'<span class="ag-flow-name">{label}</span>'
            f'</div>'
        )
    st.markdown(
        f"""
        <div class="ag-rpt-section">
            <div class="ag-rpt-sec-head">
                <span class="ag-rpt-sec-bar"></span>
                <span class="ag-rpt-sec-title">智能体执行流程</span>
            </div>
            {"".join(rows)}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================================
# 辅助函数
# =========================================================================

def _render_knowledge_basis(kb: list[dict]) -> None:
    """诊断依据：知识库命中条目（病害名 + 作物 + 典型症状）。"""
    if not kb:
        return
    rows = []
    for h in kb[:3]:
        disease = h.get("disease", "")
        crop_h = h.get("crop", "")
        symptoms = h.get("symptoms", []) or []
        detail = "　".join(symptoms[:2]) if symptoms else ""
        rows.append(
            f'<div class="ag-flow-line done">'
            f'<span class="ag-flow-mark">✓</span>'
            f'<span class="ag-flow-name">{html.escape(disease)}（{html.escape(crop_h)}）</span>'
            f'</div>'
        )
        if detail:
            rows.append(
                f'<div style="font-size:0.72rem;color:#90a4ae;padding:0 0 0.35rem 1.75rem;">'
                f'{html.escape(detail)}</div>'
            )
    st.markdown(
        f'<div class="ag-rpt-section">'
        f'<div class="ag-rpt-sec-head"><span class="ag-rpt-sec-bar"></span>'
        f'<span class="ag-rpt-sec-title">诊断依据</span></div>'
        f'{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def _render_confidence_card(result, crop, growth_stage, location, symptoms) -> None:
    """可信度评分：总分 + 五项条件勾选。"""
    from components.agent_viz import _score_confidence
    score = _score_confidence(
        result, crop=crop, growth_stage=growth_stage,
        location=location, symptoms=symptoms,
    )
    total = score["total"]
    if total >= 80:
        level, color = "高", "#1f5f3a"
    elif total >= 60:
        level, color = "中", "#0d5c63"
    elif total >= 40:
        level, color = "低", "#e67e22"
    else:
        level, color = "极低", "#c0392b"
    items_html = "".join(
        f'<div class="ag-flow-line {"done" if it["hit"] else ""}">'
        f'<span class="ag-flow-mark">{"✓" if it["hit"] else "·"}</span>'
        f'<span class="ag-flow-name">{it["name"]}</span>'
        f'</div>'
        for it in score["items"]
    )
    st.markdown(
        f'<div class="ag-rpt-section">'
        f'<div class="ag-rpt-sec-head"><span class="ag-rpt-sec-bar"></span>'
        f'<span class="ag-rpt-sec-title">可信度评分</span></div>'
        f'<div style="font-size:0.85rem;color:#546e7a;margin-bottom:0.4rem;">'
        f'诊断可信度　<b style="color:{color};">{total} / 100</b>　等级　{level}</div>'
        f'{items_html}'
        f'<div style="font-size:0.72rem;color:#90a4ae;margin-top:0.4rem;">'
        f'依据条件完整性评分，供辅助参考</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _advice_block(cls: str, title: str, body: str) -> str:
    cls_html = f' class="{cls}"' if cls else ""
    clean = _clean_markdown(body)
    body_html = "<br>".join(html.escape(ln) for ln in clean.splitlines()) if clean else ""
    return (
        f'<div class="ag-rpt-advice-block"{cls_html}>'
        f'<div class="ag-rpt-advice-title"><span class="bullet"></span>{title}</div>'
        f'<div class="ag-rpt-advice-body">{body_html}</div>'
        f'</div>'
    )


# =========================================================================
# 农户友好的结论表达
# =========================================================================

def _confidence_wording(result: dict, crop: str, growth_stage: str,
                        location: str, symptoms: str) -> dict:
    """把 0-100 的可信度分数翻译成农户能直接理解的措辞。

    农户看不懂「可信度 78/100」。这里复用 agent_viz 的评分（不新增评分逻辑，
    避免与农技员端出现两套标准），只做"分数 → 一句话"的语义映射。
    """
    from components.agent_viz import _score_confidence
    try:
        total = _score_confidence(
            result, crop=crop, growth_stage=growth_stage,
            location=location, symptoms=symptoms,
        )["total"]
    except Exception:
        total = 0

    kb = result.get("knowledge") or []
    if not kb:
        return {
            "total": total,
            "label": "信息不足",
            "color": "#c0392b",
            "advice": "本次未匹配到知识库条目，结论仅供参考，建议提交农技员确认。",
        }
    if total >= 80:
        return {
            "total": total, "label": "把握较大", "color": "#1f5f3a",
            "advice": "可按下面的方案处理；用药前请再核对一遍农药标签。",
        }
    if total >= 60:
        return {
            "total": total, "label": "比较可能", "color": "#0d5c63",
            "advice": "建议先按方案试治一块地，同时提交农技员复核。",
        }
    if total >= 40:
        return {
            "total": total, "label": "把握一般", "color": "#e67e22",
            "advice": "信息还不够，建议补拍叶背照片，或提交农技员确认后再大面积用药。",
        }
    return {
        "total": total, "label": "把握较低", "color": "#c0392b",
        "advice": "请先提交农技员确认，不要仅凭本结果大面积施药。",
    }


# =========================================================================
# 行动步骤抽取 + 配药换算
# =========================================================================

# 可直接执行的动词前缀（"立即/及时/摘除/喷施…"），优先作为行动项的第一句
_ACTION_VERBS = (
    "立即", "及时", "尽快", "马上", "摘除", "清除", "拔除", "剪除", "喷施", "喷雾",
    "喷洒", "施用", "追施", "灌水", "排水", "排涝", "通风", "加强", "注意", "避免",
    "选用", "使用", "轮换", "深埋", "销毁", "补种", "中耕",
)


def _extract_action_steps(content: str, limit: int = 3) -> list[str]:
    """从报告的防治/农事章节里抽取最多 3 条「现在要做的事」。

    只做文本抽取与清洗，不新增任何农业建议：
    优先取带可执行动词的句子；不足时用该章节的前几句补齐。
    """
    if not content:
        return []

    text = "\n".join(
        p for p in (
            _extract_section(content, "防治"),
            _extract_section(content, "农事"),
            _extract_section(content, "管理"),
        ) if p
    )
    if not text:
        text = _extract_section(content, "建议")
    if not text:
        return []

    cleaned = _clean_markdown(text)
    if not cleaned:
        return []

    candidates: list[str] = []
    for line in cleaned.splitlines():
        # 一行里可能有多个分句，按分号/句号拆开
        for piece in re.split(r"[；;。]", line):
            piece = piece.strip("　 ·-—")
            if len(piece) < 6:
                continue
            candidates.append(piece)

    priority = [c for c in candidates if c.startswith(_ACTION_VERBS)]
    rest = [c for c in candidates if c not in priority]
    ordered = priority + rest

    # 去掉互为前缀的重复（如「喷施苯醚甲环唑」与「喷施苯醚甲环唑 30ml/亩」）
    picked: list[str] = []
    for c in ordered:
        if any(c in p or p in c for p in picked):
            continue
        picked.append(c[:60] + ("…" if len(c) > 60 else ""))
        if len(picked) >= limit:
            break
    return picked


def _find_products(text: str) -> list[str]:
    """从「用药方案」原文里找出条目实际列出的产品名（登记药剂）。

    只使用界面本来就要展示的文本，不额外调用服务、不引入新事实。
    """
    if not text:
        return []
    try:
        from knowledge_center.loader import load_pesticides
        entries = load_pesticides()
    except Exception:
        return []
    names = [
        str(p.get("name") or "").strip()
        for e in (entries or [])
        for p in (e.get("products") or [])
        if isinstance(p, dict)
    ]
    return [n for n in names if n and n in text]


def _parse_dosage_terms(text: str, product: str = "") -> dict:
    """从用药文本里解析出「亩用量」「稀释倍数」「兑水量」，供配药换算。

    只解析文本里已经出现的数字，绝不自行推断或补全剂量。
    """
    terms: dict = {}
    if not text:
        return terms

    # 定位产品附近的一段文字，优先在其中解析
    scope = text
    if product and product in text:
        pos = text.index(product)
        scope = text[pos:pos + 80]

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:[-~至]\s*(\d+(?:\.\d+)?)\s*)?"
                  r"(毫升|ml|mL|克|g|kg|千克)\s*/\s*亩", scope)
    if not m:
        m = re.search(r"亩(?:用|施|用量|用量为)?\s*(\d+(?:\.\d+)?)\s*"
                      r"(?:[-~至]\s*(\d+(?:\.\d+)?)\s*)?"
                      r"(毫升|ml|mL|克|g|kg|千克)", scope)
    if m:
        terms["per_mu"] = (m.group(1), m.group(2), m.group(3))

    m = re.search(r"兑水\s*(\d+(?:\.\d+)?)\s*(kg|千克|公斤|升|L|斤)", scope)
    if m:
        terms["water_per_mu"] = (m.group(1), m.group(2))

    m = re.search(r"(\d+)\s*倍", scope)
    if m:
        terms["dilution"] = m.group(1)

    m = re.search(r"安全间隔期\s*(\d+(?:\.\d+)?)\s*天", text)
    if m:
        terms["interval"] = m.group(1)

    return terms


def _render_dosage_calculator(kb: list[dict], area: float) -> None:
    """配药用量换算：把「亩用量」变成"我这块地要买多少药、兑多少水"。

    农户最容易算错这一步（算错就是药害或无效）。所有输出都严格来自
    知识库未标注单位，除法换算仅为面积乘法，不做任何剂量推荐。
    """
    if not kb:
        return
    chem_text = " ".join(
        str(c) for h in kb[:3] for c in (h.get("registered_pesticides") or [])
    )
    # registered_pesticides 可能只是药名列表，缺少剂量，此时不展示计算器
    products = _find_products(chem_text) or [
        str(c).split()[0] for c in (kb[0].get("registered_pesticides") or []) if str(c).strip()
    ]
    if not products:
        return

    detail_text = " ".join(
        str(v)
        for h in kb[:3]
        for key in ("chemical_control", "prevention", "control_measures")
        for v in (h.get(key) or [])
    )
    terms = _parse_dosage_terms(detail_text, products[0])
    if not terms.get("per_mu") and not terms.get("water_per_mu"):
        return  # 知识库里没有剂量信息 → 不猜

    with st.expander("算算要买多少药、兑多少水", expanded=False):
        try:
            area_val = float(area)
        except (TypeError, ValueError):
            area_val = 0.0
        if area_val <= 0:
            st.info("请先在上方「补充信息」里填写地块面积。")
            return

        st.caption(f"按地块面积 {area_val:g} 亩换算（剂量取自知识库登记信息，请以农药标签为准）")
        _MU = {"毫升": 1.0, "ml": 1.0, "mL": 1.0, "克": 1.0, "g": 1.0,
               "kg": 1000.0, "千克": 1000.0}
        _W = {"kg": 1.0, "千克": 1.0, "公斤": 1.0, "升": 1.0, "L": 1.0, "斤": 0.5}

        if terms.get("per_mu"):
            lo, hi, unit = terms["per_mu"]
            factor = _MU.get(unit, 1.0)
            lo_v = float(lo) * factor / 1000.0  # 换算为 kg/L
            hi_v = float(hi) * factor / 1000.0 if hi else None
            if hi_v:
                st.markdown(
                    f"**需要药剂**　{lo_v * area_val:.2f} ～ {hi_v * area_val:.2f} "
                    f"{'升' if unit.lower() in ('ml', '毫升') else '公斤'}"
                    f"（每亩 {lo}～{hi} {unit}）"
                )
            else:
                st.markdown(
                    f"**需要药剂**　{lo_v * area_val:.2f} "
                    f"{'升' if unit.lower() in ('ml', '毫升') else '公斤'}"
                    f"（每亩 {lo} {unit}）"
                )
        if terms.get("water_per_mu"):
            w_lo, w_unit = terms["water_per_mu"]
            total = float(w_lo) * _W.get(w_unit, 1.0) * area_val
            st.markdown(f"**需要兑水**　约 {total:.0f} 公斤（每亩 {w_lo} {w_unit}）")
        if terms.get("interval"):
            st.markdown(f"**安全间隔期**　{terms['interval']} 天（采收前须停药满这个天数）")
        st.caption("以上为按面积换算的参考值，实际用量请按所购农药标签与当地植保指导确定。")


def _render_registration_card(registration: dict) -> None:
    """展示农药登记核验结果。

    只列**权威登记数据确认可用**的药剂及其登记依据；被拦截的药剂作为
    "已为你排除"提示展示，让农户知道系统挡掉了什么、为什么挡 ——
    这是本项目"不编造、可追溯"的具体体现。
    数据缺失时整块不渲染，不虚构任何登记信息。
    """
    if not registration:
        return
    candidates = registration.get("candidates") or []
    blocked = registration.get("blocked") or []
    crop = registration.get("crop") or ""
    if not candidates and not blocked:
        return

    with st.expander("农药登记核验（可放心参考的依据）", expanded=False):
        if candidates:
            st.markdown(f"**已核验可用于「{crop}」的登记药剂**")
            rows = []
            for c in candidates:
                seg = f"**{html.escape(str(c.get('name', '')))}**"
                if c.get("disease"):
                    seg += f"（登记防治对象：{html.escape(str(c['disease']))}）"
                if c.get("dosage"):
                    seg += f"　剂量：{html.escape(str(c['dosage']))}"
                if c.get("safety_interval_days"):
                    seg += f"　安全间隔期 {c['safety_interval_days']} 天"
                if c.get("max_uses_per_season"):
                    seg += f"　每季最多 {c['max_uses_per_season']} 次"
                if c.get("registration_basis"):
                    seg += f"　依据：{html.escape(str(c['registration_basis']))}"
                rows.append(f"- {seg}")
            st.markdown("\n".join(rows))
            st.caption("以上药剂来自农业农村部农药检定所登记数据核验，剂量与安全间隔期以登记标签为准。")
        else:
            st.warning(
                f"本次未能在权威登记数据中核验到可用于「{crop}」该病害的药剂。"
                "化学防治请咨询当地植保部门，按登记标签选用。"
            )

        if blocked:
            st.markdown("**已为你排除的药剂**（权威登记数据判定不可用于本作物）")
            rows = []
            for b in blocked:
                reason = str(b.get("reason") or "")
                rows.append(f"- ~~{html.escape(str(b.get('product', '')))}~~　{html.escape(reason)}")
            st.markdown("\n".join(rows))
            st.caption("这些药剂即使在某些资料中出现，也因未登记本作物而被排除，避免超范围用药风险。")


def _clean_markdown(text: str) -> str:
    """去除 Markdown 符号与 emoji，返回适合直接嵌入 HTML 的纯文本（每行一项）。"""
    if not text:
        return ""
    from components.markdown_helper import strip_emoji
    t = strip_emoji(text)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)                     # 标题符号
    t = re.sub(r"^\s*(?:\*\*|__)(.+?)(?:\*\*|__)\s*$", r"\1", t, flags=re.MULTILINE)  # 整行加粗（子标题）
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)                                   # 加粗
    t = re.sub(r"\*(.+?)\*", r"\1", t)                                       # 斜体
    t = re.sub(r"`(.+?)`", r"\1", t)                                         # 行内代码
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                           # 链接
    t = re.sub(r"^>\s?", "", t, flags=re.MULTILINE)                          # 引用符
    t = re.sub(r"^-{3,}\s*$", "", t, flags=re.MULTILINE)                     # 分隔线
    t = re.sub(r"^\|.*\|\s*$", "", t, flags=re.MULTILINE)                    # 表格行
    t = re.sub(r"^\s*(?:[-*+•]|\d+[.、)])\s*", "", t, flags=re.MULTILINE)    # 列表符号
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    return "\n".join(lines)


# 章节标题识别：兼容模型实际输出的多种写法
#   1) Markdown 标题（可带编号）：  ### 1. 初步诊断   /   ### 3. 防治方案
#   2) 同行带正文：                ### 防治方案：喷施苯醚甲环唑
#   3) 加粗短标题（可带编号）：     3. **防治方案**：xxx   /   **防治方案** 喷施…
# 旧实现只识别 "#"，而提示词要求的是编号加粗格式，导致小节永远提取为空、
# 界面上「处理建议」长期显示兜底占位文案 —— 此处按实际输出修正。
#
# 采用显式状态机而非大正则：正则的懒惰量词与可选后缀组合容易产生
# 「首次匹配吞掉正文」的隐蔽回溯行为，逐段剥离更易读也更可验证。
_NUM_PREFIX_RE = re.compile(r"^\d+\s*[.、)]\s*")


def _strip_inline_bold(text: str) -> str:
    """去掉行内加粗标记（**x** / __x__）。"""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", re.sub(r"__(.+?)__", r"\1", text)).strip()


def _parse_section_head(line: str) -> Optional[tuple[str, str, int]]:
    """把一行解析为 (标题, 正文片段, 层级)；不是标题行则返回 None。

    层级用于区分主章节与子标题，避免「#### 物理防治」被当成「### 5. 防治方案」
    的结束标志而把整段正文丢掉（真实模型输出就是这样分层的）。

    标题行仅限以下形态：
      - `### 标题` / `### 3. 标题`（层级 = # 的个数）
      - `3. **标题**：正文` / `**标题** 正文` / `**标题**`（层级 = 3）
    普通正文（如「高温高湿，田间通风差」）不会被识别为标题。
    """
    s = line.strip()
    if not s:
        return None

    # --- 1) Markdown 标题 ---
    m = re.match(r"^(#{1,6})\s+(.*)$", s)
    if m:
        head, rest = _split_head_title(m.group(2).strip())
        return head, rest, len(m.group(1))
    else:
        # --- 2) 整体加粗：**标题** 或 **标题**：正文 ---
        m = re.match(r"^(?:\d+\s*[.、)]\s*)?(?:\*\*|__)(.+?)(?:\*\*|__)\s*(.*)$", s)
        if m:
            inner = m.group(1).strip()
            tail = _strip_inline_bold(m.group(2).strip()).lstrip("：:").strip()
            # 加粗内容里若还带冒号，则冒号前是标题
            head, sep, sub = inner.partition("：")
            if not sep:
                head, sep, sub = inner.partition(":")
            if sep:
                return head.strip(), (sub + ("：" + tail if tail else "")).strip(), 3
            return inner, tail, 3
        # --- 3) 未加粗但带冒号的短标题：标题：正文 ---
        m = re.match(r"^(?P<mk>[-*+•]\s*|\d+\s*[.、)]\s*)?([^：:]{1,24})[：:]\s*(.*)$", s)
        if m:
            # 带列表标记的行（如「- 化学防治：摘除病叶」）是正文条目，不是章节标题
            if not m.group("mk"):
                head = _strip_inline_bold(m.group(2).strip())
                if head:
                    return head, m.group(3).strip(), 3
        return None


def _split_head_title(body: str) -> tuple[str, str]:
    """把 Markdown 标题正文拆成 (标题, 同行正文)。"""
    body = _NUM_PREFIX_RE.sub("", body).strip()
    head, sep, rest = body.partition("：")
    if not sep:
        head, sep, rest = body.partition(":")
    if sep:
        return head.strip(), rest.strip()
    return body.strip(), ""


def _match_section_title(title: str, keyword: str) -> bool:
    if not title or not keyword:
        return False
    return keyword in title


def _match_section_title_exact(title: str, keyword: str) -> bool:
    """精确匹配：标题以关键词开头（或关键词就是整个标题）。

    必要性：用「包含」匹配时，`### 3. 整体风险等级` 会先于 `### 7. 风险提示`
    被命中（它含"风险"），而同级标题会让提取循环在此处 break，
    真正的风险提示正文反而拿不到 —— 实测该 bug 导致卡片一直显示兜底文案。
    因此先按"以关键词开头"找；找不到再退回"包含"匹配。
    """
    if not title or not keyword:
        return False
    return title.startswith(keyword)


def _extract_section(md: str, keyword: str) -> str:
    """从诊断报告 Markdown 中提取某一章节内容（兼容多种标题格式）。

    匹配策略：优先「标题以关键词开头」（如 关键词"风险" → 「风险提示」），
    找不到再退回「标题包含关键词」。这避免「整体风险等级」抢先命中。

    章节边界按**标题层级**判定：进入「### 防治方案」后，
    遇到同级或更高级标题（如「### 6. 农事建议」）才算结束；
    而更深的子标题（如「#### 化学防治」）属于本章节内容，必须保留 ——
    否则真实输出里 "#### 物理防治" 会立刻被当作结束标志，
    导致整段防治正文丢失、界面退回兜底占位文案。

    返回该章节正文（标题行上的内容会被并入），最多 30 行 / 400 字；
    未命中返回空串，由调用方决定兜底文案。
    """
    if not md:
        return ""
    return (
        _extract_section_impl(md, keyword, exact=True)
        or _extract_section_impl(md, keyword, exact=False)
    )


def _extract_section_impl(md: str, keyword: str, exact: bool) -> str:
    matcher = _match_section_title_exact if exact else _match_section_title
    out: list[str] = []
    in_section = False
    section_level = 0

    for raw in md.split("\n"):
        line = raw.strip()
        if not line:
            continue

        parsed = _parse_section_head(line)

        if parsed is not None:
            title, rest, level = parsed
            if in_section and level <= section_level:
                # 同级或更高级标题 → 当前章节结束
                break
            if not in_section and matcher(title, keyword):
                in_section = True
                section_level = level
                if rest:
                    out.append(rest)
                continue
            if in_section:
                # 子标题：保留为正文（让农户看到"物理防治/化学防治"分项）
                out.append(line)
            continue

        if in_section:
            out.append(line)

    if not out:
        return ""

    text = "\n".join(out[:30])
    return text[:400] + ("…" if len(text) > 400 else "")


def _guess_ext(image_bytes) -> str:
    """按图片文件头判断扩展名。

    改用文件头（魔术字节）而不是上传对象的文件名，原因：
    现在"上传"与"拍照"共用一个输入区，拍照来源没有文件名，
    依赖文件名会一律退化成 png。JPEG 存成 .png 在多数查看器里能显示，
    但部分场景会解析失败，因此这里按真实字节判断。
    """
    if not image_bytes:
        return "png"
    head = bytes(image_bytes[:12])
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"GIF8"):
        return "gif"
    return "png"


# =========================================================================
# 图片输入（上传 / 拍照 共用一个框）
# =========================================================================

def _image_input_signature(image_bytes: bytes | None) -> str:
    """图片指纹：用于判断保存的图片是否已被用户更换。"""
    if not image_bytes:
        return ""
    import hashlib
    return hashlib.md5(bytes(image_bytes)).hexdigest()[:12]


def _render_image_input():
    """上传与拍照共用一个容器的图片输入区。

    为什么这样布局：农户端只有"拍一张"这一个动作，
    分成两个独立标题框会显得重复、也更容易漏看。
    这里用一个带边框的卡片统一承载「从相册选」与「直接拍照」两个入口，
    并保证同一时刻只保留一张有效图片（拍照优先，其次上传）。

    返回图片字节或 None。
    """
    st.markdown("##### 上传作物图片")

    # 来源优先级：本次会话新拍的 → 本次会话新上传的
    source = st.session_state.get("u_img_source")
    if source == "camera":
        active = st.session_state.get("u_camera")
    elif source == "upload":
        active = st.session_state.get("u_upload")
    else:
        active = st.session_state.get("u_camera") or st.session_state.get("u_upload")

    image_bytes = active.getvalue() if active is not None else None

    with st.container(border=True):
        st.caption("拍照或从相册选一张，病斑特写更清楚（可不传）")
        col_cam, col_up = st.columns(2)
        with col_cam:
            if st.button("📷 直接拍照", use_container_width=True, key="u_btn_camera"):
                st.session_state["u_img_source"] = "camera"
                st.rerun()
        with col_up:
            if st.button("🖼 从相册选择", use_container_width=True, key="u_btn_upload"):
                st.session_state["u_img_source"] = "upload"
                st.rerun()

        if source == "camera":
            cam = st.camera_input("对准病斑拍摄", key="u_camera")
            if cam is not None:
                image_bytes = cam.getvalue()
        elif source == "upload":
            up = st.file_uploader(
                "选择图片文件", type=["jpg", "jpeg", "png", "webp"], key="u_upload",
            )
            if up is not None:
                image_bytes = up.getvalue()
        else:
            st.caption("↑ 请选择一种方式")

    # 切换来源时清空另一种，避免两张图混用
    if source in ("camera", "upload"):
        for other in ("u_camera", "u_upload"):
            if other != f"u_{source}":
                st.session_state.pop(other, None)

        # 图片变化时让上一次结果失效（否则会连着旧图的结果）
        sig = _image_input_signature(image_bytes)
        if st.session_state.get("u_img_sig") != sig:
            st.session_state["u_img_sig"] = sig
            st.session_state.pop("farmer_result", None)

    if image_bytes:
        try:
            st.image(Image.open(io.BytesIO(image_bytes)), use_container_width=True)
        except Exception:
            st.error("图片解析失败，请重新选择或拍摄")
    return image_bytes


# =========================================================================
# 症状常用词（点选后并入"异常现象描述"）
# =========================================================================

def _render_symptom_quick_picks() -> None:
    """异常现象输入框下方的"常用词"下拉区。

    布局约束（按用户反馈调整）：
      - 默认**收起**，点一下才展开，避免一屏铺开十几个标签；
      - 固定在输入框所在列内，标签自动换行，**不产生横向滚动**。

    实现说明：Streamlit 不允许把控件嵌入 `st.text_area` 内部，
    因此这里紧贴输入框下方、同一列内呈现，视觉上仍属于"异常现象"这一栏。
    """
    with st.expander("常用词（点一下填入，可多选）", expanded=False):
        st.pills(
            "症状常用词", CHIP_LABELS, selection_mode="multi",
            key="u_symptom_picks", label_visibility="collapsed",
            width="stretch",
        )
        picked = st.session_state.get("u_symptom_picks") or []
        if picked:
            st.caption("已选：" + "、".join(str(p) for p in picked))


def _compose_symptoms(typed: str) -> str:
    """把"手输描述"与"点选常用词"合成检索/诊断用文本（按用词去重）。"""
    typed = (typed or "").strip()
    picked = st.session_state.get("u_symptom_picks") or []
    picked_text = build_symptom_text(list(picked))
    if not typed:
        return picked_text
    if not picked_text:
        return typed
    # 逐个并入，且与"已累积的结果"比较，避免同一用词出现两次
    merged = typed
    appended = False
    for token in picked_text.split("、"):
        if token and token not in merged:
            merged += "；" + token
            appended = True
    return merged if appended else typed


def _submit_task(*, image_bytes, image_ext, crop, growth_stage, soil_type,
                 area, location, symptoms, ai_result) -> None:
    try:
        task_id = memory.record_task(
            location=location, crop=crop, growth_stage=growth_stage,
            soil_type=soil_type, area=area, symptoms=symptoms,
            image_bytes=image_bytes, image_ext=image_ext,
            farmer_name=st.session_state.get("farmer_name", ""),
            contact=st.session_state.get("farmer_contact", ""),
            ai_result=ai_result,
        )
        st.session_state["farmer_last_task"] = task_id
        # 新提交优先展示：清掉旧的查询结果，避免新工单被旧查询遮挡
        st.session_state["farmer_query_task"] = None
        st.session_state["farmer_query_input"] = ""
        st.success(f"工单已提交，编号 TK-{task_id[-6:].upper()}")
        _render_task_status_card(task_id)
    except Exception:
        st.error("提交失败，请稍后重试")


# =========================================================================
# 审核进度：工单状态页 + 审核结果
# =========================================================================

def _short_id(task_id: str) -> str:
    return f"TK-{task_id[-6:].upper()}"


def _find_task_by_short(query: str):
    """按短编号或完整编号查找工单。"""
    q = (query or "").strip().upper()
    if not q:
        return None
    for t in memory.list_tasks():
        if q in (t["task_id"], _short_id(t["task_id"])):
            return t
    return None


def _render_task_status_card(task_id: str) -> None:
    task = memory.get_task(task_id)
    if not task:
        st.info("未找到该工单，可能已被删除。")
        return

    status = task.get("status", "待审核")
    display = task_status_display(status)
    published = bool(task.get("publish_time"))
    reviewing = status in ("处理中", "已完成", "已关闭")

    # ---- 提交后三步链 ----
    st.markdown(
        f"""
        <div class="ag-rpt-section">
            <div class="ag-rpt-sec-head">
                <span class="ag-rpt-sec-bar"></span>
                <span class="ag-rpt-sec-title">工单进度</span>
            </div>
            {flow_steps_html([
                ("AI 分析完成", "done"),
                ("已生成智能诊断报告", "done"),
                ("已提交农技员审核", "done"),
            ], vertical=True)}
            <div style="margin-top:0.7rem;font-size:0.8rem;line-height:2;color:#546e7a;">
                工单编号　<b>{_short_id(task_id)}</b><br>
                提交时间　{fmt_cn_time(task.get('create_time', ''))}<br>
                当前状态　<b>{display}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- 四步流转：农户提交 → AI分析 → 专家审核 → 方案发布 ----
    flow_steps = [
        ("农户提交", "done"),
        ("AI分析", "done"),
        ("专家审核", "done" if (reviewing or published) else "current"),
        ("方案发布", "done" if published else ("current" if reviewing else "pending")),
    ]
    st.markdown(
        f"""
        <div class="ag-rpt-section">
            <div class="ag-rpt-sec-head">
                <span class="ag-rpt-sec-bar"></span>
                <span class="ag-rpt-sec-title">处理流转</span>
            </div>
            {flow_steps_html(flow_steps)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- 审核结果 ----
    if published:
        st.success("农技员已完成审核　最终方案已生成")
        ai = task.get("ai_result", {})
        with st.expander("查看审核结果", expanded=True):
            st.markdown("AI 初步诊断")
            from components.markdown_helper import plain_report_html
            st.markdown(plain_report_html(ai.get("content", "")), unsafe_allow_html=True)
            st.markdown("农技员审核意见")
            st.markdown(task.get("final_diagnosis") or "未填写")
            st.markdown("最终防治建议")
            st.markdown(task.get("final_recommendation") or "未填写")
            st.markdown(f"审核时间　{fmt_cn_time(task.get('publish_time', ''))}")
    elif reviewing:
        st.info("农技员正在审核中，请稍后刷新本页查看结果。")


diagnose_clicked = False
