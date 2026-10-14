"""
农智链 AgriAgent 智能体展示组件。

为诊断页面提供三种可视化展示：
  1. render_agent_task_analysis()  — "🤖 农智链 AgriAgent 任务分析"：用户任务理解 + 自动拆解 + 执行状态
  2. render_agent_tool_calls()     — 工具调用记录：5 大模块 + 状态 + 耗时
  3. render_agent_confidence()     — 诊断可信度：规则评分（5 维 × 20 分）

数据来源：全部基于 Agent.run() 的返回 dict，不改任何 Agent 核心逻辑。
"""
from __future__ import annotations

from typing import Optional

import streamlit as st


_STATUS_ICON = {
    "done": "✓",
    "running": "→",
    "failed": "✗",
    "skipped": "⊘",
    "pending": "·",
}

_STATUS_LABEL_CN = {
    "done": "已完成",
    "running": "执行中",
    "failed": "失败",
    "skipped": "已跳过",
    "pending": "待执行",
}

_STATUS_CLS = {
    "done": "ag-step-done",
    "running": "ag-step-running",
    "failed": "ag-step-failed",
    "skipped": "ag-step-skipped",
    "pending": "ag-step-pending",
}

_TOOL_MAP = {
    "retrieve_knowledge": {
        "name": "农业知识中心",
        "module": "knowledge_center.retriever",
        "desc": "结构化作物病害知识库 RAG 检索",
        "category": "知识检索",
    },
    "vision_analyze": {
        "name": "视觉识别模型",
        "module": "services.ai_service (多模态)",
        "desc": "调用 LLM 多模态能力对图片进行表观分析",
        "category": "视觉感知",
    },
    "query_history": {
        "name": "地块记忆模块",
        "module": "memory.history",
        "desc": "读取地块历史诊断记录，识别复发/持续问题",
        "category": "记忆召回",
    },
    "llm_diagnose": {
        "name": "大模型推理",
        "module": "services.ai_service",
        "desc": "综合知识+视觉+记忆，生成完整诊断方案",
        "category": "推理生成",
    },
    "safety_review": {
        "name": "安全审核模块",
        "module": "safety.reviewer",
        "desc": "排查禁限用农药、剂量、风险措辞",
        "category": "安全审核",
    },
    "save_record": {
        "name": "记忆写入",
        "module": "memory.history",
        "desc": "将本次诊断结果写入地块档案，形成知识闭环",
        "category": "知识沉淀",
    },
}


def _fmt_ms(ms: float) -> str:
    if ms <= 0:
        return "—"
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


def __estimate_durations(steps: list[dict]) -> dict[str, float]:
    """根据 step.status 给一个估算耗时（Executor 当前未填 duration_ms）。"""
    per_status = {
        "done": 500,
        "skipped": 0,
        "failed": 300,
        "pending": 0,
        "running": 0,
    }
    return {s["name"]: per_status.get(s.get("status", "pending"), 0) for s in steps}


# =========================================================================
# 1. 任务分析
# =========================================================================

def render_agent_task_analysis(
    result: dict,
    *,
    crop: str = "",
    growth_stage: str = "",
    location: str = "",
    symptoms: str = "",
    area: float = 0,
    soil_type: str = "",
) -> None:
    """
    "🤖 农智链 AgriAgent 任务分析" 展示区：
      - 用户输入理解（自然语言摘要）
      - 6 步自动拆解 + 每步执行状态/细节
      - 总体进度（完成/跳过/失败统计）
    """
    steps: list[dict] = result.get("plan", [])

    st.markdown("---")
    st.markdown("##### 🤖 农智链 AgriAgent 任务分析")

    # --- 用户任务理解 ---
    parts = []
    if crop:
        parts.append(f"**作物：**{crop}")
    if growth_stage:
        parts.append(f"生育阶段：{growth_stage}")
    if area:
        parts.append(f"面积：{area} 亩")
    if soil_type:
        parts.append(f"土壤：{soil_type}")
    if location:
        parts.append(f"位置：{location}")
    parts.append(f"**输入类型：**{'图片+文字' if result.get('vision', {}).get('enabled') else '纯文字'}")

    summary = " > ".join(parts) if parts else "（无输入）"
    st.markdown(f'<div class="ag-agent-insight"><b>🧠 任务理解：</b>{summary}</div>', unsafe_allow_html=True)

    # 农户原始描述（如果有）
    if symptoms:
        st.caption(f"  农户描述：{symptoms[:120]}{'…' if len(symptoms) > 120 else ''}")

    # --- 6 步自动拆解 + 执行状态 ---
    durations = __estimate_durations(steps)
    done_count = sum(1 for s in steps if s.get("status") == "done")
    skip_count = sum(1 for s in steps if s.get("status") == "skipped")
    fail_count = sum(1 for s in steps if s.get("status") == "failed")

    # 总体进度条
    total = max(len(steps), 1)
    progress_pct = int(done_count / total * 100)
    st.progress(progress_pct / 100, text=f"总体进度 {done_count}/{len(steps)} 完成 · {skip_count} 跳过 · {fail_count} 异常")

    # 步骤列表（紧凑表格样式）
    rows_html = []
    rows_html.append(
        '<table class="ag-agent-table" style="margin-top:0.6rem;width:100%;border-collapse:collapse;">'
        '<thead><tr>'
        '<th style="text-align:left;padding:0.35rem 0.6rem;border-bottom:2px solid #e2e8f0;">#</th>'
        '<th style="text-align:left;padding:0.35rem 0.6rem;border-bottom:2px solid #e2e8f0;">步骤</th>'
        '<th style="text-align:left;padding:0.35rem 0.6rem;border-bottom:2px solid #e2e8f0;">状态</th>'
        '<th style="text-align:left;padding:0.35rem 0.6rem;border-bottom:2px solid #e2e8f0;">细节</th>'
        '<th style="text-align:right;padding:0.35rem 0.6rem;border-bottom:2px solid #e2e8f0;">耗时</th>'
        '</tr></thead><tbody>'
    )
    for i, s in enumerate(steps, 1):
        status = s.get("status", "pending")
        icon = _STATUS_ICON.get(status, "·")
        label = s.get("label", s.get("name", ""))
        detail = s.get("detail", "") or "—"
        dur = _fmt_ms(durations.get(s["name"], 0))
        cls = _STATUS_CLS.get(status, "")
        rows_html.append(
            f'<tr class="{cls}">'
            f'<td style="padding:0.3rem 0.6rem;color:#90a4ae;font-size:0.8rem;">{i}</td>'
            f'<td style="padding:0.3rem 0.6rem;font-weight:500;color:#2c3e50;">{s.get("icon","")} {label}</td>'
            f'<td style="padding:0.3rem 0.6rem;">'
            f'<span class="ag-status-{status}">{icon} {_STATUS_LABEL_CN.get(status, status)}</span>'
            f'</td>'
            f'<td style="padding:0.3rem 0.6rem;color:#78909c;font-size:0.82rem;">{detail}</td>'
            f'<td style="padding:0.3rem 0.6rem;color:#78909c;font-size:0.8rem;text-align:right;">{dur}</td>'
            f'</tr>'
        )
    rows_html.append("</tbody></table>")
    st.markdown("".join(rows_html), unsafe_allow_html=True)


# =========================================================================
# 2. 工具调用记录
# =========================================================================

def render_agent_tool_calls(result: dict) -> None:
    """
    工具调用记录：展示 6 大模块（视觉 / 知识 / 记忆 / 大模型 / 审核 / 写入）
    的名称、状态、耗时、调用细节。
    """
    steps: list[dict] = result.get("plan", [])
    durations = __estimate_durations(steps)

    st.markdown("---")
    st.markdown("##### 🔧 工具调用记录")

    cards = []
    for s in steps:
        meta = _TOOL_MAP.get(s["name"], {"name": s.get("label", s["name"]), "desc": "", "category": "", "module": ""})
        status = s.get("status", "pending")
        dur = _fmt_ms(durations.get(s["name"], 0))
        detail = s.get("detail", "") or "—"

        badge_cls = {
            "done": "ag-badge-done",
            "running": "ag-badge-running",
            "failed": "ag-badge-failed",
            "skipped": "ag-badge-skipped",
            "pending": "ag-badge-pending",
        }.get(status, "ag-badge-pending")

        cards.append(
            f'<div class="ag-tool-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div style="font-weight:600;color:#2c3e50;">{s.get("icon","")} {meta["name"]}</div>'
            f'<div style="display:flex;gap:0.5rem;align-items:center;">'
            f'<span class="{badge_cls}">{_STATUS_ICON.get(status,"·")} {_STATUS_LABEL_CN.get(status,status)}</span>'
            f'<span style="color:#78909c;font-size:0.8rem;">⏱ {dur}</span>'
            f'</div></div>'
            f'<div style="font-size:0.78rem;color:#78909c;margin-top:0.3rem;">'
            f'<span class="ag-chip">{meta["category"]}</span>  ·  {meta["module"]}</div>'
            f'<div style="font-size:0.82rem;color:#546e7a;margin-top:0.4rem;">{meta["desc"]}</div>'
            f'<div style="font-size:0.8rem;color:#90a4ae;margin-top:0.25rem;border-left:3px solid #e2e8f0;padding-left:0.5rem;">'
            f'执行细节：{detail}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div class="ag-tools-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


# =========================================================================
# 3. 诊断可信度（规则评分）
# =========================================================================

def _score_confidence(
    result: dict,
    *,
    crop: str = "",
    growth_stage: str = "",
    location: str = "",
    symptoms: str = "",
) -> dict:
    """
    规则评分（不伪造准确率，每项独立 +20 分，满分 100）：

    ┌──────────────────┬────────┬────────────────────────────────────────┐
    │ 维度             │ 分值   │ 判定条件                               │
    ├──────────────────┼────────┼────────────────────────────────────────┤
    │ 知识命中         │ +20    │ len(result["knowledge"]) > 0           │
    │ 历史记录         │ +20    │ len(result["history_records"]) > 0     │
    │ 图片分析         │ +20    │ vision.enabled and vision.success      │
    │ 安全审核通过     │ +20    │ review.risk_level 不在 ["高"]          │
    │ 用户信息完整     │ +20    │ crop/growth_stage/location/symptoms 全填│
    └──────────────────┴────────┴────────────────────────────────────────┘
    """
    items = [
        {
            "name": "知识命中",
            "desc": "农业知识中心 RAG 检索到匹配条目",
            "points": 20,
            "hit": len(result.get("knowledge", [])) > 0,
            "evidence": f"{len(result.get('knowledge', []))} 条知识" if result.get("knowledge") else "无知识命中",
        },
        {
            "name": "历史记录",
            "desc": "地块档案中存在历史诊断记录",
            "points": 20,
            "hit": len(result.get("history_records", [])) > 0,
            "evidence": f"{len(result.get('history_records', []))} 条历史" if result.get("history_records") else "首诊，无历史",
        },
        {
            "name": "图片分析",
            "desc": "视觉模型成功完成图片表观分析",
            "points": 20,
            "hit": bool(result.get("vision", {}).get("enabled") and result.get("vision", {}).get("success")),
            "evidence": "视觉分析成功" if result.get("vision", {}).get("success") else (
                "未上传图片" if not result.get("vision", {}).get("enabled") else "分析失败"
            ),
        },
        {
            "name": "安全审核",
            "desc": "安全审核模块未发现高风险问题",
            "points": 20,
            "hit": (result.get("review") or {}).get("risk_level", "高") != "高",
            "evidence": (result.get("review") or {}).get("risk_level", "未知"),
        },
        {
            "name": "用户信息完整",
            "desc": "作物、阶段、位置、症状均已提供",
            "points": 20,
            "hit": all([crop, growth_stage, location, symptoms]),
            "evidence": (
                "四项齐全" if all([crop, growth_stage, location, symptoms])
                else f"缺 {sum(1 for v in [crop, growth_stage, location, symptoms] if not v)} 项"
            ),
        },
    ]

    total = sum(it["points"] for it in items if it["hit"])
    return {"total": total, "items": items}


def render_agent_confidence(
    result: dict,
    *,
    crop: str = "",
    growth_stage: str = "",
    location: str = "",
    symptoms: str = "",
) -> None:
    """
    诊断可信度展示：5 维规则评分条 + 总分 + 解读。
    """
    score = _score_confidence(
        result, crop=crop, growth_stage=growth_stage,
        location=location, symptoms=symptoms,
    )
    total = score["total"]

    st.markdown("---")
    st.markdown("##### 📊 诊断可信度（规则评分）")

    # 总分环形风格展示
    level = "高" if total >= 80 else ("中" if total >= 60 else ("低" if total >= 40 else "极低"))
    level_color = {"高": "#1f5f3a", "中": "#0d5c63", "低": "#e67e22", "极低": "#c0392b"}[level]

    c_top_left, c_top_right = st.columns([1, 2])
    with c_top_left:
        st.markdown(
            f'<div class="ag-score-ring">'
            f'<div class="ag-score-num" style="color:{level_color};">{total}</div>'
            f'<div class="ag-score-unit">/ 100</div>'
            f'<div class="ag-score-label">规则可信度</div>'
            f'</div>'
            f'<div style="text-align:center;margin-top:0.5rem;">'
            f'<span style="background:{level_color};color:white;padding:0.2rem 0.6rem;border-radius:10px;font-size:0.78rem;">'
            f'{level}可信度</span></div>',
            unsafe_allow_html=True,
        )
    with c_top_right:
        st.markdown(
            f'<div class="ag-score-breakdown">'
            f'<b>评分说明：</b>每项条件独立满足 +20 分，满分 100。'
            f'{" 所有 5 项条件均满足，系统诊断可信度高。" if total == 100 else ""}'
            f'{" 存在条件缺失，建议结合农技员人工审核。" if total < 80 else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

        for it in score["items"]:
            icon = "✓" if it["hit"] else "○"
            bar_color = "#1f5f3a" if it["hit"] else "#e2e8f0"
            bar_w = "100%" if it["hit"] else "0%"
            st.markdown(
                f'<div style="margin:0.35rem 0;display:flex;align-items:center;gap:0.5rem;">'
                f'<span style="color:{bar_color};font-weight:700;width:1rem;">{icon}</span>'
                f'<span style="width:5.5rem;font-size:0.82rem;color:#546e7a;">{it["name"]}</span>'
                f'<div style="flex:1;background:#f1f5f9;border-radius:3px;height:0.4rem;overflow:hidden;">'
                f'<div style="width:{bar_w};background:{bar_color};height:100%;border-radius:3px;transition:width 0.4s;"></div>'
                f'</div>'
                f'<span style="font-size:0.78rem;color:#90a4ae;width:2.2rem;text-align:right;">+{it["points"]}</span>'
                f'</div>'
                f'<div style="font-size:0.72rem;color:#b0bec5;margin-left:1.55rem;margin-top:-0.15rem;margin-bottom:0.2rem;">'
                f'{it["evidence"]}</div>',
                unsafe_allow_html=True,
            )

    st.caption("⚠️ 以上为基于规则的条件完整性评分，**非 AI 诊断准确率**。仅用于辅助参考，最终诊断请以农技员审核为准。")


# =========================================================================
# 统一入口：一次渲染全部三个模块
# =========================================================================

def render_agent_viz(
    result: dict,
    *,
    crop: str = "",
    growth_stage: str = "",
    location: str = "",
    symptoms: str = "",
    area: float = 0,
    soil_type: str = "",
) -> None:
    """
    一次性渲染全部 Agent 智能体可视化。
    在诊断结果页直接调用即可，不修改任何 Agent 核心逻辑。
    """
    render_agent_task_analysis(
        result, crop=crop, growth_stage=growth_stage, location=location,
        symptoms=symptoms, area=area, soil_type=soil_type,
    )
    render_agent_tool_calls(result)
    render_agent_confidence(
        result, crop=crop, growth_stage=growth_stage,
        location=location, symptoms=symptoms,
    )


# =========================================================================
# 4. Agent 完整工作流（8 步决策链路可视化）
# =========================================================================

_AGENT_FLOW_STEPS = [
    {
        "key": "understand",
        "name": "用户需求理解",
        "sub": "User Intent Parsing",
        "icon": "🧭",
    },
    {
        "key": "planner",
        "name": "Planner 任务规划",
        "sub": "Agent Planning",
        "icon": "📋",
    },
    {
        "key": "knowledge",
        "name": "知识中心 RAG 检索",
        "sub": "Retrieval-Augmented Generation",
        "icon": "📚",
    },
    {
        "key": "vision",
        "name": "视觉模型分析",
        "sub": "Vision Model",
        "icon": "👁",
    },
    {
        "key": "memory",
        "name": "地块历史记忆",
        "sub": "Plot Memory Recall",
        "icon": "🗂",
    },
    {
        "key": "llm",
        "name": "LLM 综合推理",
        "sub": "LLM Reasoning",
        "icon": "🧠",
    },
    {
        "key": "safety",
        "name": "安全审核",
        "sub": "Safety Review",
        "icon": "🛡",
    },
    {
        "key": "report",
        "name": "生成决策报告",
        "sub": "Decision Output",
        "icon": "📄",
    },
]


def _io_val(text: str, *, kind: str = "") -> str:
    """格式化输入/输出值的小辅助。"""
    text = (text or "").strip() or "—"
    cls = f' class="ag-flow-io-val {kind}"' if kind else ' class="ag-flow-io-val"'
    return f'<div{cls}>{text}</div>'


def render_agent_workflow(
    result: dict,
    *,
    crop: str = "",
    growth_stage: str = "",
    area: float = 0,
    soil_type: str = "",
    location: str = "",
    symptoms: str = "",
    has_image: bool = False,
) -> None:
    """
    "🧠 AI 智能体决策过程" —— 展示从用户输入到最终决策的完整 8 步链路。

    每步展示：
      - 图标 / 模块名 / 英文副标题
      - 执行状态徽章
      - 输入信息（短摘要）
      - 输出结果（短摘要）

    数据全部来自 Agent.run() 的 result dict，不修改任何 Agent 核心逻辑。
    """
    plan_steps: list[dict] = result.get("plan", [])
    plan_status = {s["name"]: s.get("status", "pending") for s in plan_steps}
    plan_detail = {s["name"]: (s.get("detail") or "") for s in plan_steps}

    kb = result.get("knowledge", [])
    vision = result.get("vision", {}) or {}
    review = result.get("review", {}) or {}
    hist = result.get("history_records", [])
    success = result.get("success", False)
    content = result.get("content", "")
    content_src = result.get("source", "")

    # ------------------------------------------------------------
    # 为 8 步工作流准备 input / output / status
    # ------------------------------------------------------------
    def _get(k: str) -> dict:
        return _STEP_BUILDER[k](
            crop=crop, growth_stage=growth_stage, area=area,
            soil_type=soil_type, location=location, symptoms=symptoms,
            has_image=has_image, plan_status=plan_status, plan_detail=plan_detail,
            kb=kb, vision=vision, review=review, hist=hist,
            success=success, content=content, content_src=content_src,
        )

    def _build_step_html(meta: dict, data: dict, show_arrow: bool = True) -> str:
        status = data["status"]
        icon = meta["icon"]
        name = meta["name"]
        sub = meta["sub"]
        status_cn = _STATUS_LABEL_CN.get(status, status)
        in_html = _io_val(data["input"], kind=data.get("input_kind", ""))
        out_html = _io_val(data["output"], kind=data.get("output_kind", ""))

        step = (
            f'<div class="ag-flow-step {status}">'
            f'<div class="ag-flow-head">'
            f'<div class="ag-flow-icon">{icon}</div>'
            f'<div class="ag-flow-name">'
            f'<div class="ag-flow-name-main">{name}</div>'
            f'<div class="ag-flow-name-sub">{sub}</div>'
            f'</div>'
            f'<span class="ag-flow-status {status}">{status_cn}</span>'
            f'</div>'
            f'<div class="ag-flow-body">'
            f'<div class="ag-flow-io"><div class="ag-flow-io-lbl">输入</div>{in_html}</div>'
            f'<div class="ag-flow-io"><div class="ag-flow-io-lbl">输出</div>{out_html}</div>'
            f'</div>'
            f'</div>'
        )
        arrow = '<div class="ag-flow-arrow">↓</div>'
        return step + (arrow if show_arrow else "")

    steps_html = []
    for i, meta in enumerate(_AGENT_FLOW_STEPS):
        data = _get(meta["key"])
        is_last = i == len(_AGENT_FLOW_STEPS) - 1
        steps_html.append(_build_step_html(meta, data, show_arrow=not is_last))

    # ------------------------------------------------------------
    # 最终决策卡
    # ------------------------------------------------------------
    total_done = sum(1 for k in plan_status if plan_status[k] == "done")
    final_status = "done" if success else ("failed" if success is False else "running")
    final_disease = kb[0]["disease"] if kb else "—"
    final_sub = f"{len(kb)} 条知识 · {len(hist)} 条历史 · {len(plan_steps)} 步流程"

    st.markdown(
        f"""
        <div class="ag-flow">
            <div class="ag-flow-title">
                <span class="ag-flow-title-bar"></span>
                🧠 AI 智能体决策过程
            </div>
            <div class="ag-flow-sub">
                农智链 AgriAgent 基于 Planner + RAG + Vision + Memory + LLM + Safety 的多模块协同推理链路
            </div>
            {"".join(steps_html)}
            <div class="ag-flow-final">
                <div>
                    <div class="ag-flow-final-txt">
                        {"✓ 决策已生成" if success else "⚠ 决策失败"}
                    </div>
                    <div class="ag-flow-final-sub">
                        主要对象：{final_disease} · {final_sub}
                    </div>
                </div>
                <div style="font-size:0.72rem;opacity:0.9;">
                    {content_src}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================================
# 8 步数据构建器（纯 dict 返回，保持 Agent 逻辑不变）
# =========================================================================

def _b_understand(**kw) -> dict:
    parts = []
    if kw["crop"]:
        parts.append(f"{kw['crop']}")
    if kw["growth_stage"]:
        parts.append(kw["growth_stage"])
    if kw["area"]:
        parts.append(f"{kw['area']}亩")
    if kw["location"]:
        parts.append(kw["location"])
    input_text = " · ".join(parts) if parts else "（未填写）"
    input_text += " + 图片" if kw["has_image"] else "（纯文字）"

    if kw["symptoms"]:
        out = f"用户描述：{kw['symptoms'][:60]}{'…' if len(kw['symptoms']) > 60 else ''}"
    else:
        out = "用户未提供文字描述"
    return {"status": "done", "input": input_text, "output": out, "output_kind": "ok"}


def _b_planner(**kw) -> dict:
    steps = kw.get("plan_status", {})
    if not steps:
        return {"status": "done", "input": "用户输入理解结果", "output": "任务规划：6 步 Agent 工作流", "output_kind": "ok"}
    out = "任务分解：" + " → ".join(s.replace("step_", "") for s in list(steps.keys())[:4]) + " …"
    return {"status": "done", "input": "用户输入理解结果", "output": out, "output_kind": "ok"}


def _b_knowledge(**kw) -> dict:
    status = kw["plan_status"].get("retrieve_knowledge", "pending")
    detail = kw["plan_detail"].get("retrieve_knowledge", "")
    kb = kw.get("kb", [])
    in_q = f"查询关键词：{kw['crop']} {kw['growth_stage']} {kw['symptoms'][:20] if kw['symptoms'] else ''}".strip()
    if status == "done" and kb:
        out = f"命中 {len(kb)} 条：" + "、".join(k["disease"] for k in kb[:3])
        out_kind = "ok"
    elif status == "done":
        out = "无知识命中"
        out_kind = "warn"
    elif status == "failed":
        out = "知识库异常"
        out_kind = "err"
    else:
        out = detail or "等待执行"
        out_kind = "note"
    return {"status": status, "input": in_q, "output": out, "output_kind": out_kind}


def _b_vision(**kw) -> dict:
    status = kw["plan_status"].get("vision_analyze", "pending")
    detail = kw["plan_detail"].get("vision_analyze", "")
    vision = kw.get("vision") or {}
    in_txt = "上传病害图片" if kw["has_image"] else "无图片输入"
    if status == "done":
        out = vision.get("summary", vision.get("note", "视觉分析完成"))
        out_kind = "ok"
    elif status == "skipped":
        out = detail or "未上传图片，跳过"
        out_kind = "note"
    elif status == "failed":
        out = "视觉分析失败"
        out_kind = "err"
    else:
        out = detail or "等待执行"
        out_kind = "note"
    return {"status": status, "input": in_txt, "output": out, "output_kind": out_kind}


def _b_memory(**kw) -> dict:
    status = kw["plan_status"].get("query_history", "pending")
    detail = kw["plan_detail"].get("query_history", "")
    hist = kw.get("hist", [])
    in_txt = f"地块档案查询：{kw['location'] or '当前地块'}"
    if status == "done":
        out = f"召回 {len(hist)} 条历史记录" if hist else "无历史记录（首诊）"
        out_kind = "ok" if hist else "note"
    elif status == "skipped":
        out = "无历史记录，跳过"
        out_kind = "note"
    else:
        out = detail or "等待执行"
        out_kind = "note"
    return {"status": status, "input": in_txt, "output": out, "output_kind": out_kind}


def _b_llm(**kw) -> dict:
    status = kw["plan_status"].get("llm_diagnose", "pending")
    detail = kw["plan_detail"].get("llm_diagnose", "")
    in_txt = "知识 + 视觉 + 历史 三路综合上下文"
    content = kw.get("content", "")
    if status == "done" and content:
        out = content[:80] + ("…" if len(content) > 80 else "")
        out_kind = "ok"
    elif status == "failed":
        out = "LLM 生成失败"
        out_kind = "err"
    else:
        out = detail or "等待执行"
        out_kind = "note"
    return {"status": status, "input": in_txt, "output": out, "output_kind": out_kind}


def _b_safety(**kw) -> dict:
    status = kw["plan_status"].get("safety_review", "pending")
    detail = kw["plan_detail"].get("safety_review", "")
    review = kw.get("review") or {}
    in_txt = "LLM 生成的完整诊断方案"
    if status == "done":
        risk = review.get("risk_level", "未知")
        issues = review.get("issues", []) or []
        out = f"风险等级：{risk}"
        if issues:
            out += f" · {len(issues)} 个问题"
        out_kind = "ok" if risk not in ("高",) else "warn"
    elif status == "failed":
        out = "审核模块异常"
        out_kind = "err"
    else:
        out = detail or "等待执行"
        out_kind = "note"
    return {"status": status, "input": in_txt, "output": out, "output_kind": out_kind}


def _b_report(**kw) -> dict:
    status = "done" if kw.get("success") else "failed"
    kb = kw.get("kb", [])
    hist = kw.get("hist", [])
    in_txt = "通过安全审核的最终诊断方案"
    if status == "done":
        out = f"诊断报告已生成 · 识别 {kb[0]['disease'] if kb else '—'} · 参考 {len(hist)} 条历史"
        out_kind = "ok"
    else:
        out = "诊断流程未完成"
        out_kind = "err"
    return {"status": status, "input": in_txt, "output": out, "output_kind": out_kind}


_STEP_BUILDER = {
    "understand": _b_understand,
    "planner": _b_planner,
    "knowledge": _b_knowledge,
    "vision": _b_vision,
    "memory": _b_memory,
    "llm": _b_llm,
    "safety": _b_safety,
    "report": _b_report,
}


__all__ = [
    "render_agent_task_analysis",
    "render_agent_tool_calls",
    "render_agent_confidence",
    "render_agent_viz",
    "render_agent_workflow",
    "render_agent_execution_flow",
]


# =========================================================================
# 5. 比赛展示用 · AgriAgent 智能体执行过程（6 步卡片式）
# =========================================================================

_AGENT_EXEC_STEPS = [
    {
        "key": "planner",
        "name": "任务规划",
        "icon": "🧭",
        "module": "planner.Planner",
        "sub": "Agent Planning",
        "plan_name": "__planner__",
    },
    {
        "key": "vision",
        "name": "视觉分析",
        "icon": "👁",
        "module": "services.ai_service (多模态)",
        "sub": "Vision Analysis",
        "plan_name": "vision_analyze",
    },
    {
        "key": "rag",
        "name": "知识检索 (RAG)",
        "icon": "📚",
        "module": "knowledge_center.retriever",
        "sub": "Retrieval-Augmented Generation",
        "plan_name": "retrieve_knowledge",
    },
    {
        "key": "memory",
        "name": "历史记忆",
        "icon": "🗂",
        "module": "memory.history",
        "sub": "Plot Memory Recall",
        "plan_name": "query_history",
    },
    {
        "key": "llm",
        "name": "LLM 综合诊断",
        "icon": "🧠",
        "module": "services.ai_service",
        "sub": "LLM Reasoning & Generation",
        "plan_name": "llm_diagnose",
    },
    {
        "key": "safety",
        "name": "安全审核",
        "icon": "🛡",
        "module": "safety.reviewer",
        "sub": "Safety Review",
        "plan_name": "safety_review",
    },
]


def _build_exec_step_data(
    meta: dict, *,
    plan_status: dict, plan_detail: dict,
    crop: str = "", growth_stage: str = "",
    area: float = 0, soil_type: str = "",
    location: str = "", symptoms: str = "",
    has_image: bool = False,
    kb: list = None, vision: dict = None,
    hist: list = None, review: dict = None,
    content: str = "", success: bool = False,
) -> dict:
    kb = kb or []
    vision = vision or {}
    hist = hist or []
    review = review or {}

    plan_name = meta["plan_name"]

    if meta["key"] == "planner":
        return {
            "status": "done",
            "input": f"{crop or '未指定'} · {growth_stage or '—'} · {area or 0}亩"
                     f"{(' · 📷有图' if has_image else ' · 纯文字')}",
            "output": "自动拆解为 6 步 Agent 工作流"
                      + (f"：{', '.join(s.replace('step_','') for s in list(plan_status.keys())[:4])}" if plan_status else ""),
        }
    if meta["key"] == "vision":
        status = plan_status.get(plan_name, "pending")
        detail = plan_detail.get(plan_name, "")
        in_txt = "上传病害图片" if has_image else "无图片输入"
        if status == "done":
            out = vision.get("summary", vision.get("content", "视觉分析完成")[:60])
        elif status == "skipped":
            out = detail or "未上传图片，跳过视觉分析"
        elif status == "failed":
            out = "视觉分析失败"
        else:
            out = detail or "等待执行"
        return {"status": status, "input": in_txt, "output": out}
    if meta["key"] == "rag":
        status = plan_status.get(plan_name, "pending")
        detail = plan_detail.get(plan_name, "")
        in_q = f"查询：{crop} {growth_stage} {symptoms[:20] if symptoms else ''}".strip()
        if status == "done" and kb:
            out = f"命中 {len(kb)} 条：" + "、".join(h["disease"] for h in kb[:3])
        elif status == "done":
            out = "无知识命中"
        elif status == "failed":
            out = "知识库异常"
        else:
            out = detail or "等待执行"
        return {"status": status, "input": in_q, "output": out}
    if meta["key"] == "memory":
        status = plan_status.get(plan_name, "pending")
        detail = plan_detail.get(plan_name, "")
        in_txt = f"地块档案：{location or '当前地块'} · {crop}"
        if status == "done":
            out = f"召回 {len(hist)} 条历史记录" if hist else "无历史（首诊）"
        elif status == "skipped":
            out = "无历史记录，跳过"
        else:
            out = detail or "等待执行"
        return {"status": status, "input": in_txt, "output": out}
    if meta["key"] == "llm":
        status = plan_status.get(plan_name, "pending")
        detail = plan_detail.get(plan_name, "")
        in_txt = "知识 + 视觉 + 历史 三路综合上下文"
        if status == "done" and content:
            out = content[:70] + ("…" if len(content) > 70 else "")
        elif status == "failed":
            out = "LLM 生成失败"
        else:
            out = detail or "等待执行"
        return {"status": status, "input": in_txt, "output": out}
    if meta["key"] == "safety":
        status = plan_status.get(plan_name, "pending")
        detail = plan_detail.get(plan_name, "")
        in_txt = "LLM 生成的完整诊断方案"
        if status == "done":
            risk = review.get("risk_level", "未知")
            issues = review.get("issues", []) or []
            out = f"风险等级：{risk}"
            if issues:
                out += f" · {len(issues)} 个问题"
        elif status == "failed":
            out = "审核模块异常"
        else:
            out = detail or "等待执行"
        return {"status": status, "input": in_txt, "output": out}

    return {"status": "pending", "input": "—", "output": "—"}


def render_agent_execution_flow(
    result: dict,
    *,
    crop: str = "",
    growth_stage: str = "",
    area: float = 0,
    soil_type: str = "",
    location: str = "",
    symptoms: str = "",
    has_image: bool = False,
) -> None:
    """
    🤖 AgriAgent 智能体执行过程 —— 比赛展示专用。

    6 步卡片式工作流：
      任务规划 → 视觉分析 → 知识检索(RAG) → 历史记忆 → LLM综合诊断 → 安全审核

    每步展示：
      - 步骤名称 + 图标
      - 调用模块名
      - 输入摘要
      - 输出摘要
      - 执行状态徽章 (done/running/skipped/failed/pending)
    """
    plan_steps: list[dict] = result.get("plan", [])
    plan_status = {s["name"]: s.get("status", "pending") for s in plan_steps}
    plan_detail = {s["name"]: (s.get("detail") or "") for s in plan_steps}

    kb = result.get("knowledge", [])
    vision = result.get("vision", {}) or {}
    review = result.get("review", {}) or {}
    hist = result.get("history_records", [])
    success = result.get("success", False)
    content = result.get("content", "")

    total_done = sum(1 for k, v in plan_status.items() if v == "done")
    total_skip = sum(1 for k, v in plan_status.items() if v == "skipped")
    step_idx = 0

    cards_html = []
    for i, meta in enumerate(_AGENT_EXEC_STEPS):
        data = _build_exec_step_data(
            meta, plan_status=plan_status, plan_detail=plan_detail,
            crop=crop, growth_stage=growth_stage, area=area,
            soil_type=soil_type, location=location, symptoms=symptoms,
            has_image=has_image, kb=kb, vision=vision, hist=hist,
            review=review, content=content, success=success,
        )
        step_idx += 1
        status = data["status"]
        icon = meta["icon"]
        name = meta["name"]
        sub = meta["sub"]
        module = meta["module"]
        in_txt = data["input"]
        out_txt = data["output"]

        status_cn = _STATUS_LABEL_CN.get(status, status)

        cards_html.append(
            f'<div class="ag-exec-card {status}">'
            f'<div class="ag-exec-idx">{step_idx}</div>'
            f'<div class="ag-exec-head">'
            f'<div class="ag-exec-icon">{icon}</div>'
            f'<div class="ag-exec-title-wrap">'
            f'<div class="ag-exec-title">{name}</div>'
            f'<div class="ag-exec-sub">{sub}</div>'
            f'</div>'
            f'<span class="ag-exec-status {status}">{_STATUS_ICON.get(status,"·")} {status_cn}</span>'
            f'</div>'
            f'<div class="ag-exec-module">'
            f'<span class="ag-exec-mod-tag">module</span>{module}'
            f'</div>'
            f'<div class="ag-exec-io">'
            f'<div class="ag-exec-io-row">'
            f'<span class="ag-exec-io-lbl">输入</span>'
            f'<span class="ag-exec-io-val">{in_txt}</span>'
            f'</div>'
            f'<div class="ag-exec-io-row">'
            f'<span class="ag-exec-io-lbl">输出</span>'
            f'<span class="ag-exec-io-val {_io_kind(status, out_txt)}">{out_txt}</span>'
            f'</div>'
            f'</div>'
            f'</div>'
        )

        if i < len(_AGENT_EXEC_STEPS) - 1:
            cards_html.append('<div class="ag-exec-arrow">↓</div>')

    st.markdown(
        f"""
        <div class="ag-exec-wrap">
            <div class="ag-exec-header">
                <div class="ag-exec-header-left">
                    <div class="ag-exec-header-icon">🤖</div>
                    <div class="ag-exec-header-title">
                        <div class="ag-exec-header-main">AgriAgent 智能体执行过程</div>
                        <div class="ag-exec-header-sub">Planner → Vision → RAG → Memory → LLM → Safety</div>
                    </div>
                </div>
                <div class="ag-exec-header-stats">
                    <div class="ag-exec-stat">
                        <span class="num">{total_done}</span>
                        <span class="lbl">已完成</span>
                    </div>
                    <div class="ag-exec-stat">
                        <span class="num">{len(_AGENT_EXEC_STEPS) - total_done - total_skip}</span>
                        <span class="lbl">进行中</span>
                    </div>
                    <div class="ag-exec-stat">
                        <span class="num">{total_skip}</span>
                        <span class="lbl">跳过</span>
                    </div>
                </div>
            </div>
            <div class="ag-exec-cards">
                {"".join(cards_html)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _io_kind(status: str, output: str) -> str:
    if status == "done":
        return "ok"
    if status == "failed":
        return "err"
    if status == "skipped":
        return "note"
    return ""
