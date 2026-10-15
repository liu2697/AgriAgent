from __future__ import annotations

import json
from typing import Optional

from agent.planner import (
    AgentPlan, AgentStep,
    STEP_RETRIEVE_KNOWLEDGE, STEP_VISION_ANALYZE,
    STEP_QUERY_HISTORY, STEP_LLM_DIAGNOSE,
    STEP_SAFETY_REVIEW, STEP_SAVE_RECORD,
)
from agent.knowledge import KnowledgeService
from agent.memory import MemoryService
from agent.safety import SafetyService, ReviewResult
from knowledge_center.registration import (
    sanitize_pesticide_mentions, registration_disclaimer,
)
from services.ai_service import diagnose as llm_diagnose

MOCK_SOURCE = "mock"


def source_label(src: str) -> str:
    """对外展示的来源文案。

    原则：**调不到大模型时必须写明**，不能让人误以为内容是大模型输出。
    """
    s = (src or "").strip()
    low = s.lower()
    if low == MOCK_SOURCE:
        return "农智链 AgriAgent · 示例模式（未配置 AI 服务密钥）"
    if low == "error":
        return "农智链 AgriAgent · 调用失败"
    return f"农智链 AgriAgent · {s}".strip() if s else "农智链 AgriAgent"


class Executor:
    """
    农业智能体任务执行器（Step Registry 调度版）。

    不再硬编码调用 6 个步骤函数，而是：
        1. 按 Step Registry（步骤注册表）维护 step.name → handler 的映射
        2. 遍历 Planner 产出的 plan.steps，按步骤名查找 handler 并自动执行
        3. 步骤间通过共享工作区（workspace）传递中间结果
        4. 执行完毕后按原有结构组装最终返回结果

    保留：on_step 进度回调、running/done/failed/skipped 状态更新、
    每步内部异常捕获、最终返回结果结构、6 个功能步骤逻辑。
    """

    # ------------------------------------------------------------------
    # Step Registry：步骤名 → 处理函数（方法名）
    # ------------------------------------------------------------------
    STEP_REGISTRY: dict[str, str] = {
        STEP_RETRIEVE_KNOWLEDGE: "_step_retrieve_knowledge",
        STEP_VISION_ANALYZE: "_step_vision_analyze",
        STEP_QUERY_HISTORY: "_step_query_history",
        STEP_LLM_DIAGNOSE: "_step_llm_diagnose",
        STEP_SAFETY_REVIEW: "_step_safety_review",
        STEP_SAVE_RECORD: "_step_save_record",
    }

    def __init__(self):
        self.knowledge = KnowledgeService()
        self.memory = MemoryService()
        self.safety = SafetyService()

    # ------------------------------------------------------------
    # 主入口：按 Plan 动态调度
    # ------------------------------------------------------------
    def execute(self, plan: AgentPlan, image_bytes: Optional[bytes],
                crop: str, growth_stage: str, soil_type: str,
                area: float, location: str, symptoms: str,
                enable_memory: bool, on_step) -> dict:

        ctx = {
            "image_bytes": image_bytes,
            "crop": crop,
            "growth_stage": growth_stage,
            "soil_type": soil_type,
            "area": area,
            "location": location,
            "symptoms": symptoms,
            "enable_memory": enable_memory,
        }

        # 共享工作区：步骤间的中间结果都写在这里
        ws: dict = {}

        # ---- 按 Plan 逐步调度执行（替代原硬编码 6 次调用） ----
        for step in plan.steps:
            handler_name = self.STEP_REGISTRY.get(step.name)
            handler = getattr(self, handler_name, None) if handler_name else None
            if handler is None:
                step.status = "failed"
                step.detail = f"未注册的步骤：{step.name}"
                on_step(step)
                continue
            try:
                handler(step, ctx, ws, on_step)
            except Exception as exc:
                step.status = "failed"
                step.detail = f"步骤执行异常：{exc}"
                on_step(step)

        # ---- 汇总工作区结果（保留原有返回结构） ----
        knowledge_hits = ws.get("knowledge_hits", [])
        vision_result = ws.get("vision_result", {"enabled": False})
        history_records = ws.get("history_records", [])
        history_summary = ws.get("history_summary", "")
        llm_result = ws.get(
            "llm_result",
            {"success": False, "content": "LLM 步骤未执行", "source": "error"},
        )
        review_result = ws.get("review_result") or ReviewResult(
            safe=True, risk_level="未知", issues=[]
        )
        memory_record = ws.get("memory_record")

        # 组装最终报告
        final_content = self._compose_final_report(
            base_content=llm_result.get("content", ""),
            knowledge_hits=knowledge_hits,
            vision_result=vision_result,
            review_result=review_result,
            history_count=len(history_records),
        )

        # 对**整份最终报告**再做一次登记合规清理。
        # 必要性：审核步骤已清理了 LLM 正文，但 _compose_final_report 拼装的
        # "知识库参考 / 登记药剂"区块来自知识库原始字段，会绕过上一步，
        # 实测仍在报告里展示「登记药剂 苯醚甲环唑、丙环唑」等未登记药剂 ——
        # 等于从后门把超范围用药递给了农户。这里统一兜住。
        try:
            top_disease = str(knowledge_hits[0].get("disease") or "") if knowledge_hits else ""
            # 关键：传入**显式名单**（知识库命中条目标注的药剂 + 上一步已剔除的），
            # 不再做形态推导。形态推导会与正文里的合规长名重叠，出现
            # 「吡唑醚菌酯」被拆成「吡唑〔已移除〕」这类误伤（实测踩过）。
            # 需要清理的目标本来就是"确定出现在报告里的知识库药剂名"，用名单最精确。
            explicit: list[str] = []
            for h in knowledge_hits[:3]:
                for v in (h.get("registered_pesticides") or []):
                    v = str(v).strip()
                    if v and v not in explicit:
                        explicit.append(v)
            for r in (ws.get("registration_removed") or []):
                nm = str(r.get("product") or "").strip()
                if nm and nm not in explicit:
                    explicit.append(nm)

            final_content, removed_2 = sanitize_pesticide_mentions(
                final_content, crop, top_disease, names=explicit,
            )
            if removed_2:
                already = {r["product"] for r in (ws.get("registration_removed") or [])}
                merged = list(ws.get("registration_removed") or [])
                for r in removed_2:
                    if r["product"] not in already:
                        merged.append(r)
                ws["registration_removed"] = merged
                note = registration_disclaimer(removed_2)
                if note:
                    final_content = note + "\n\n" + final_content
        except Exception:
            # 清理失败不得让诊断整体失败，但也不能假装清理成功：
            # review 已把问题记进审核记录，界面会按 risk_level 提示。
            pass

        return {
            "success": llm_result.get("success", False),
            "content": final_content,
            "source": source_label(llm_result.get("source", "")),
            "plan": [s.to_dict() for s in plan.steps],
            "knowledge": knowledge_hits,
            "vision": vision_result,
            "review": review_result.to_dict(),
            "review_summary": review_result.summary_text(),
            "registration": ws.get("registration") or {},
            "registration_removed": ws.get("registration_removed") or [],
            "history_records": history_records,
            "memory_record": memory_record,
        }

    # ------------------------------------------------------------
    # Step 1: 病害知识库检索
    # ------------------------------------------------------------
    def _step_retrieve_knowledge(self, step: AgentStep, ctx: dict, ws: dict, on_step) -> None:
        step.status = "running"
        on_step(step)
        try:
            query = f"{ctx['crop']} {ctx['growth_stage']} {ctx['symptoms']}".strip()
            hits = self.knowledge.search(query, crop_hint=ctx["crop"], top_k=3)
            step.detail = f"命中 {len(hits)} 条知识条目"
            if hits:
                step.detail += "：" + "、".join(h["disease"] for h in hits[:3])
            step.status = "done"
        except Exception as exc:
            hits = []
            step.detail = f"知识库检索异常：{exc}"
            step.status = "failed"
        ws["knowledge_hits"] = hits
        on_step(step)

    # ------------------------------------------------------------
    # Step 2: 视觉图片分析（复用 LLM 多模态能力）
    # ------------------------------------------------------------
    def _step_vision_analyze(self, step: AgentStep, ctx: dict, ws: dict, on_step) -> None:
        step.status = "running"
        on_step(step)

        image_bytes = ctx.get("image_bytes")

        if not image_bytes:
            step.detail = "未上传图片，跳过视觉分析（纯文字模式）"
            step.status = "skipped"
            ws["vision_result"] = {"enabled": False, "note": "无图片输入"}
            on_step(step)
            return

        try:
            result = llm_diagnose(
                image_bytes=image_bytes,
                crop=ctx["crop"],
                growth_stage=ctx["growth_stage"],
                soil_type=ctx["soil_type"],
                area=ctx["area"],
                location=ctx["location"],
                symptoms="",
                vision_only=True,
            )
            src = result.get("source", "unknown")
            if src == MOCK_SOURCE:
                # 未配置密钥：图片其实没有被模型看过，必须如实标注，
                # 否则最终报告会出现"已结合视觉分析结果"这种不实描述。
                step.detail = "视觉分析未执行 · 示例模式（未配置 AI 服务密钥，图片未参与分析）"
                step.status = "skipped"
                ws["vision_result"] = {
                    "enabled": True,
                    "success": False,
                    "content": result.get("content", "")[:800],
                    "source": src,
                }
            else:
                step.detail = f"视觉分析完成 · 来源：{src}"
                step.status = "done" if result.get("success") else "failed"
                ws["vision_result"] = {
                    "enabled": True,
                    "success": result.get("success", False),
                    "content": result.get("content", "")[:800],
                    "source": src,
                }
        except Exception as exc:
            step.detail = f"视觉分析异常：{exc}"
            step.status = "failed"
            ws["vision_result"] = {"enabled": True, "success": False, "error": str(exc)}
        on_step(step)

    # ------------------------------------------------------------
    # Step 3: 查询历史地块记录
    # ------------------------------------------------------------
    def _step_query_history(self, step: AgentStep, ctx: dict, ws: dict, on_step) -> None:
        step.status = "running"
        on_step(step)
        try:
            records = self.memory.get_history(
                ctx["location"], ctx["crop"], ctx["area"], limit=5
            )
            summary = self.memory.summarize_history(
                ctx["location"], ctx["crop"], ctx["area"]
            )
            step.detail = (
                f"召回 {len(records)} 条历史记录"
                if records else "无历史记录（首诊）"
            )
            step.status = "done"
        except Exception as exc:
            records, summary = [], ""
            step.detail = f"历史查询异常：{exc}"
            step.status = "failed"
        ws["history_records"] = records
        ws["history_summary"] = summary
        on_step(step)

    # ------------------------------------------------------------
    # Step 4: 调用千问/LLM 生成诊断方案
    # ------------------------------------------------------------
    def _step_llm_diagnose(self, step: AgentStep, ctx: dict, ws: dict, on_step) -> None:
        step.status = "running"
        on_step(step)
        try:
            # 药剂登记合规核验（事前白名单）：先算出本作物下哪些药剂确实已登记，
            # 哪些属于超范围用药，再连同约束一起交给 LLM。
            reg = self._registration_constraints(
                crop=ctx["crop"], knowledge_hits=ws.get("knowledge_hits", []),
            )
            ws["registration"] = reg

            augmented = self._augment_prompt(
                crop=ctx["crop"], growth_stage=ctx["growth_stage"],
                soil_type=ctx["soil_type"], area=ctx["area"],
                location=ctx["location"], symptoms=ctx["symptoms"],
                knowledge_hits=ws.get("knowledge_hits", []),
                vision_result=ws.get("vision_result", {}),
                history_summary=ws.get("history_summary", ""),
                registration=reg,
            )
            result = llm_diagnose(
                image_bytes=ctx.get("image_bytes"),
                crop=ctx["crop"], growth_stage=ctx["growth_stage"],
                soil_type=ctx["soil_type"], area=ctx["area"],
                location=ctx["location"], symptoms=augmented,
            )
            _src = result.get("source", "unknown")
            step.detail = ("LLM 来源：示例模式（未配置 AI 服务密钥，内容为内置示例）"
                           if _src == MOCK_SOURCE else f"LLM 来源：{_src}")
            if reg.get("candidates"):
                step.detail += f"；登记核验通过药剂 {len(reg['candidates'])} 个"
            step.status = "done" if result.get("success") else "failed"
        except Exception as exc:
            result = {"success": False, "content": f"LLM 调用失败：{exc}", "source": "error"}
            step.detail = str(exc)
            step.status = "failed"
        ws["llm_result"] = result
        on_step(step)

    @staticmethod
    def _registration_constraints(crop: str, knowledge_hits: list[dict]) -> dict:
        """按候选病害算出「可推荐药剂」与「被拦截药剂」。

        只依据 knowledge_center.registration（即 pesticide.json 权威登记数据），
        不生成任何新农业事实。知识库未收录的药剂归入 unverified，既不放行
        也不断言违法，而是提示需核对标签。
        """
        from knowledge_center.registration import filter_recommendable, registered_products_for

        candidates: list[dict] = []
        blocked: list[dict] = []
        seen_blocked: set[str] = set()
        for hit in knowledge_hits or []:
            disease = str(hit.get("disease") or "")
            listed = [str(v) for v in (hit.get("registered_pesticides") or [])]
            keep, drop = filter_recommendable(listed, crop, disease)
            for name in keep:
                if not any(c["name"] == name for c in candidates):
                    # 附上权威剂量/安全间隔期，优先于历史条目的旧剂量
                    detail = next(
                        (p for p in registered_products_for(crop, disease)
                         if p["name"] == name), None,
                    )
                    candidates.append({
                        "name": name,
                        "disease": disease,
                        "dosage": (detail or {}).get("dosage", ""),
                        "safety_interval_days": (detail or {}).get("safety_interval_days"),
                        "max_uses_per_season": (detail or {}).get("max_uses_per_season"),
                        "registration_basis": (detail or {}).get("registration_basis", ""),
                    })
            for item in drop:
                if item["product"] in seen_blocked:
                    continue
                seen_blocked.add(item["product"])
                blocked.append({**item, "disease": disease})

        return {
            "candidates": candidates,
            "blocked": blocked,
            "crop": crop,
        }

    # ------------------------------------------------------------
    # Step 5: 调用安全审核模块
    # ------------------------------------------------------------
    def _step_safety_review(self, step: AgentStep, ctx: dict, ws: dict, on_step) -> None:
        step.status = "running"
        on_step(step)
        try:
            hits = ws.get("knowledge_hits", []) or []
            top_disease = str(hits[0].get("disease") or "") if hits else ""
            raw_content = ws.get("llm_result", {}).get("content", "")

            review = self.safety.review(
                text=raw_content,
                diagnosis_context=json.dumps(ws.get("knowledge_hits", []), ensure_ascii=False),
                crop=ctx.get("crop", ""),
                disease=top_disease,
            )

            # 硬拦截：把未通过登记核验的药剂名从最终报告正文中剔除。
            # 仅"标记问题"不够 —— 农户会照着正文用药；审核记录保留原始文本作为
            # 证据（raw_content 已进入 review 的扫描范围），对外内容必须是清理过的。
            cleaned, removed = sanitize_pesticide_mentions(
                raw_content, ctx.get("crop", ""), top_disease,
            )
            if removed:
                ws["registration_removed"] = removed
                llm_result = ws.get("llm_result") or {}
                llm_result["content"] = cleaned
                llm_result["redacted"] = [r["product"] for r in removed]
                ws["llm_result"] = llm_result
                step.detail = (
                    f"风险等级：{review.risk_level}，发现 {len(review.issues)} 个问题；"
                    f"已剔除未登记药剂 {len(removed)} 个"
                )
            else:
                step.detail = (
                    f"风险等级：{review.risk_level}，"
                    f"发现 {len(review.issues)} 个问题"
                )
            step.status = "done"
        except Exception as exc:
            review = ReviewResult(safe=True, risk_level="未知", issues=[])
            step.detail = f"安全审核异常：{exc}"
            step.status = "failed"
        ws["review_result"] = review
        on_step(step)

    # ------------------------------------------------------------
    # Step 6: 保存诊断记录
    # ------------------------------------------------------------
    def _step_save_record(self, step: AgentStep, ctx: dict, ws: dict, on_step) -> None:
        step.status = "running"
        on_step(step)

        llm_result = ws.get("llm_result", {})
        review_result = ws.get("review_result")

        if not ctx.get("enable_memory") or not llm_result.get("success"):
            step.detail = "记忆已禁用或无可写入内容"
            step.status = "skipped"
            ws["memory_record"] = None
            on_step(step)
            return

        try:
            summary_lines = []
            for line in llm_result["content"].splitlines():
                line = line.strip().lstrip("-* ")
                if line and len(line) > 6:
                    summary_lines.append(line)
                    if len(summary_lines) >= 4:
                        break
            record = self.memory.record_visit(
                location=ctx["location"], crop=ctx["crop"],
                growth_stage=ctx["growth_stage"], area=ctx["area"],
                diagnosis=summary_lines[0] if summary_lines else "",
                recommendation="\n".join(summary_lines[1:4]),
                note="AGENT_V2",
                risk_level=review_result.risk_level if review_result else "",
            )
            step.detail = f"已写入地块记忆（{record['plot_key']}）"
            step.status = "done"
        except Exception as exc:
            record = None
            step.detail = f"保存失败：{exc}"
            step.status = "failed"
        ws["memory_record"] = record
        on_step(step)

    # ------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------
    @staticmethod
    def _augment_prompt(*, crop, growth_stage, soil_type, area, location,
                        symptoms, knowledge_hits: list[dict],
                        vision_result: dict, history_summary: str,
                        registration: dict | None = None) -> str:
        sections = []

        if knowledge_hits:
            lines = ["【知识库检索命中】（你的诊断必须从以下条目中选择）"]
            for h in knowledge_hits:
                lines.append(f"\n■ {h['disease']}（相关性 {h['relevance_score']}）")
                sym = h.get("symptoms") or []
                if sym:
                    lines.append("  典型症状：" + "；".join(str(s) for s in sym[:4]))
                feats = h.get("diagnosis_features") or []
                if feats:
                    lines.append("  诊断特征：" + "；".join(str(f) for f in feats[:3]))
                pests = h.get("registered_pesticides") or []
                if pests:
                    lines.append(
                        "  知识库历史标注药剂（**未经登记核验，仅为资料，不得直接推荐**）："
                        + "、".join(str(p) for p in pests[:5])
                    )
                prev = h.get("prevention") or []
                if prev:
                    lines.append("  防治要点：" + "；".join(str(p) for p in prev[:3]))
            sections.append("\n".join(lines))
        else:
            sections.append(
                "【知识库检索命中】无。当前知识库中没有与描述匹配的条目。\n"
                "请注意：这不代表田间没有问题。你必须明确说明“本次未能匹配到知识库条目，"
                "结论仅供参考，建议尽快联系当地农技人员”，并且不要编造具体药剂名称与剂量。"
            )

        if vision_result.get("enabled") and vision_result.get("content"):
            sections.append("【视觉分析初步描述】\n" + vision_result["content"])

        if history_summary:
            sections.append(history_summary)

        if registration:
            sections.append(Executor._registration_section(registration))

        if sections:
            prefix = (
                "以下是系统为你检索到的农业知识、权威农药登记核验结果、视觉分析结果"
                "与该地块历史记录，请综合这些信息后给出专业诊断与建议：\n\n"
            )
            return prefix + "\n\n".join(sections) + "\n\n农户原始描述：" + (symptoms or "")

        return symptoms

    @staticmethod
    def _registration_section(registration: dict) -> str:
        """把农药登记核验结果格式化为 Prompt 约束段。

        这是**法律底线约束**：只有权威登记数据确认的药剂才允许出现在用药建议里。
        """
        candidates = registration.get("candidates") or []
        blocked = registration.get("blocked") or []
        crop = registration.get("crop") or ""

        lines = ["【农药登记核验结果】（法律底线，必须严格遵守）"]

        if candidates:
            lines.append(
                f"以下药剂已通过权威登记核验（{crop} 上登记对象与本次诊断相符），"
                "**化学防治只能从这些药剂中选择**："
            )
            for c in candidates:
                seg = f"  · {c['name']}"
                if c.get("disease"):
                    seg += f"（登记用于：{c['disease']}）"
                if c.get("dosage"):
                    seg += f"；权威剂量：{c['dosage']}"
                if c.get("safety_interval_days"):
                    seg += f"；安全间隔期 {c['safety_interval_days']} 天"
                if c.get("max_uses_per_season"):
                    seg += f"；每季最多 {c['max_uses_per_season']} 次"
                lines.append(seg)
        else:
            lines.append(
                f"本次诊断未能在权威登记数据中核验到可用于「{crop}」上述病害的药剂。"
                "化学防治部分必须写“本平台未核验到登记药剂，请咨询当地植保部门按登记标签选用”，"
                "**不得推荐任何具体药名与剂量**。"
            )

        if blocked:
            lines.append(
                "以下药剂**禁止推荐**（权威登记数据判定不可用于本作物，属超范围用药，"
                "即使历史资料或常识中提到也不得采用）："
            )
            for b in blocked:
                lines.append(f"  ✗ {b['product']}：{b.get('reason', '')}")

        lines.append(
            "注意：知识库里标注的“历史标注药剂”“登记药剂”字段**未经过登记核验**，"
            "其中可能包含未登记本作物的药剂（如苯醚甲环唑的现行登记作物不含玉米），"
            "一律不得直接采用。剂量以权威剂量为准，禁止使用历史资料中的“倍液”表述。"
        )
        return "\n".join(lines)

    @staticmethod
    def _compose_final_report(base_content: str, knowledge_hits: list[dict],
                              vision_result: dict, review_result: ReviewResult,
                              history_count: int) -> str:
        parts: list[str] = []

        if vision_result.get("enabled") and vision_result.get("success"):
            parts.append("> 已结合视觉分析结果。")

        if knowledge_hits:
            kb_lines = ["### 知识库参考"]
            for h in knowledge_hits[:3]:
                kb_lines.append(f"- **{h['disease']}**（{h['crop']}　相关性 {h['relevance_score']}）")
                if h.get("symptoms"):
                    kb_lines.append(f"  - 典型症状　{' '.join(h['symptoms'][:3])}")
                if h.get("registered_pesticides"):
                    kb_lines.append(f"  - 登记药剂　{' '.join(h['registered_pesticides'][:3])}")
            parts.append("\n".join(kb_lines))

        if history_count > 0:
            parts.append(f"> 已结合该地块 **{history_count}** 条历史诊断记录进行参考。")

        parts.append(base_content)
        parts.append(review_result.summary_text())

        return "\n\n".join(p for p in parts if p)


__all__ = ["Executor"]
