from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from knowledge.base import dump_knowledge
from memory import history as _memory


# ---------------------------------------------------------------------------
# Step 定义（保留原 AgentStep 数据结构）
# ---------------------------------------------------------------------------

@dataclass
class AgentStep:
    """智能体任务步骤，贯穿 Planner → Executor → UI 全链路。"""
    name: str
    label: str
    description: str
    icon: str = ""
    status: str = "pending"       # pending | running | done | failed | skipped
    detail: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentPlan:
    """由 Planner 产出的任务计划。"""
    steps: list[AgentStep] = field(default_factory=list)
    ctx: dict = field(default_factory=dict)

    def add(self, step: AgentStep) -> None:
        self.steps.append(step)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

# 标准步骤名（Executor 契约：Executor 按名字查找并依次执行，名称不可缺失）
STEP_RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
STEP_VISION_ANALYZE = "vision_analyze"
STEP_QUERY_HISTORY = "query_history"
STEP_LLM_DIAGNOSE = "llm_diagnose"
STEP_SAFETY_REVIEW = "safety_review"
STEP_SAVE_RECORD = "save_record"

# 内置知识库覆盖的作物（用于判断作物是否可命中专题条目）
_KNOWN_CROPS = {entry["crop"] for entry in json.loads(dump_knowledge())}


class Planner:
    """
    农业智能体任务规划器（动态规划版）。

    由固定 6 步模板升级为「条件驱动的动态任务规划」：
        1. 评估输入条件：是否上传图片 / 作物类型是否有内置知识 / 是否存在地块历史
        2. 按条件动态生成每个步骤的状态与描述：
           - 有图片 → 执行视觉分析；无图片 → 标记 skipped（跳过）
           - 有历史 → 执行历史召回；无历史 → 标记 skipped（首诊，跳过历史分析）
           - 作物命中知识库 → 检索该作物专题条目；否则说明按通用知识兜底
        3. 条件判断结果同时写入 plan.ctx["conditions"] 供后续链路复用

    说明：6 个标准步骤名是 Executor 的执行契约（Executor 按名查找步骤），
    因此动态性体现在「条件化状态/描述 + 条件上下文」上，而不是删减步骤名。
    """

    # 标准步骤模板（基线定义，plan() 会按条件逐条定制）
    STEP_TEMPLATE = [
        AgentStep(
            name=STEP_RETRIEVE_KNOWLEDGE,
            label="病害知识检索",
            icon="📚",
            description="从内置农业知识库中检索该作物的常见病虫害与登记药剂",
        ),
        AgentStep(
            name=STEP_VISION_ANALYZE,
            label="视觉图片分析",
            icon="👁️",
            description="调用视觉模型对上传的作物图片进行病害识别",
        ),
        AgentStep(
            name=STEP_QUERY_HISTORY,
            label="历史记录查询",
            icon="📜",
            description="查询该地块的历史诊断记录，识别是否为复发或持续问题",
        ),
        AgentStep(
            name=STEP_LLM_DIAGNOSE,
            label="防治方案生成",
            icon="🧠",
            description="基于知识库+视觉分析+历史记录，调用 LLM 生成完整诊断方案",
        ),
        AgentStep(
            name=STEP_SAFETY_REVIEW,
            label="安全审核",
            icon="🔒",
            description="对生成的防治方案进行安全审核，排查禁限用农药与风险措辞",
        ),
        AgentStep(
            name=STEP_SAVE_RECORD,
            label="保存诊断记录",
            icon="💾",
            description="将本次诊断结果写入地块历史记忆，形成长期知识闭环",
        ),
    ]

    # ------------------------------------------------------------------
    # 条件评估
    # ------------------------------------------------------------------
    def _evaluate_conditions(self, image_bytes: Optional[bytes], crop: str,
                             growth_stage: str, soil_type: str, area: float,
                             location: str, symptoms: str) -> dict:
        """根据用户输入评估任务条件。"""
        has_image = image_bytes is not None

        # 是否存在该地块的历史诊断记录（只读查询，不修改记忆）
        history_records: list[dict] = []
        try:
            history_records = _memory.get_history(location, crop, area, limit=5)
        except Exception:
            history_records = []
        has_history = len(history_records) > 0

        # 作物类型是否在内置知识库覆盖范围内
        crop_known = crop in _KNOWN_CROPS

        return {
            "has_image": has_image,
            "has_history": has_history,
            "history_count": len(history_records),
            "crop": crop,
            "crop_known": crop_known,
            "growth_stage": growth_stage,
            "soil_type": soil_type,
            "area": area,
            "location": location,
            "symptoms": symptoms,
            "mode": "图片 + 文字" if has_image else "纯文字",
        }

    # ------------------------------------------------------------------
    # 条件步骤生成
    # ------------------------------------------------------------------
    def _build_step(self, tpl: AgentStep, cond: dict) -> AgentStep:
        """按条件动态生成单个步骤（状态 / 描述随输入变化）。"""
        step = AgentStep(
            name=tpl.name,
            label=tpl.label,
            icon=tpl.icon,
            description=tpl.description,
            status="pending",
        )

        if tpl.name == STEP_RETRIEVE_KNOWLEDGE:
            if cond["crop_known"]:
                step.description = (
                    f"从内置知识库检索「{cond['crop']}」常见病虫害与登记药剂"
                    f"（当前阶段：{cond['growth_stage']}）"
                )
            else:
                step.description = (
                    f"作物「{cond['crop']}」暂无内置专题条目，"
                    "按通用病虫害知识兜底检索"
                )

        elif tpl.name == STEP_VISION_ANALYZE:
            if cond["has_image"]:
                step.description = "调用视觉模型对上传的作物图片进行病害特征识别"
            else:
                step.status = "skipped"
                step.description = (
                    "未上传图片 → 条件不满足，跳过视觉分析（自动降级为纯文字模式）"
                )

        elif tpl.name == STEP_QUERY_HISTORY:
            if cond["has_history"]:
                step.description = (
                    f"该地块已有 {cond['history_count']} 条历史诊断，"
                    "召回最近记录，辅助判断复发/持续问题"
                )
            else:
                step.status = "skipped"
                step.description = (
                    "该地块无历史诊断记录（首诊）→ 条件不满足，跳过历史分析"
                )

        elif tpl.name == STEP_LLM_DIAGNOSE:
            refs = []
            if cond["crop_known"]:
                refs.append("知识库")
            if cond["has_history"]:
                refs.append("历史记录")
            base = f"综合{'、'.join(refs)}与" if refs else ""
            step.description = (
                f"{base}用户描述，以「{cond['mode']}」模式调用 LLM 生成诊断方案"
            )

        elif tpl.name == STEP_SAFETY_REVIEW:
            # 固定步骤：任何输入都必须经过安全审核
            step.description = (
                "对生成的防治方案进行安全审核（禁限用农药 + 剂量复核 + 风险措辞）"
            )

        elif tpl.name == STEP_SAVE_RECORD:
            step.description = (
                f"将本次诊断写入地块档案「{cond['location'] or '未命名地块'}」"
            )

        return step

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def plan(self, image_bytes: Optional[bytes], crop: str, growth_stage: str,
             soil_type: str, area: float, location: str,
             symptoms: str) -> AgentPlan:
        """
        根据用户输入动态生成任务计划。

        流程：评估输入条件 → 按条件逐条定制 6 个标准步骤（状态/描述）→ 组装计划。
        """
        cond = self._evaluate_conditions(
            image_bytes=image_bytes, crop=crop, growth_stage=growth_stage,
            soil_type=soil_type, area=area, location=location, symptoms=symptoms,
        )

        # 保留原有 ctx 键，并新增条件判断结果
        ctx = {
            "has_image": cond["has_image"],
            "crop": crop,
            "growth_stage": growth_stage,
            "soil_type": soil_type,
            "area": area,
            "location": location,
            "symptoms": symptoms,
            "conditions": cond,
        }

        plan = AgentPlan(ctx=ctx)
        for tpl in self.STEP_TEMPLATE:
            plan.add(self._build_step(tpl, cond))

        return plan


__all__ = [
    "AgentStep",
    "AgentPlan",
    "Planner",
    "STEP_RETRIEVE_KNOWLEDGE",
    "STEP_VISION_ANALYZE",
    "STEP_QUERY_HISTORY",
    "STEP_LLM_DIAGNOSE",
    "STEP_SAFETY_REVIEW",
    "STEP_SAVE_RECORD",
]
