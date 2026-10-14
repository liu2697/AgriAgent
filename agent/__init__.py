from __future__ import annotations

from typing import Optional, Callable

from agent.planner import Planner, AgentPlan, AgentStep
from agent.executor import Executor
from agent.knowledge import KnowledgeService
from agent.memory import MemoryService
from agent.safety import SafetyService, ReviewResult


class AgriAgent:
    """
    农业智能体主入口。
    采用 Planner → Executor 分层架构：
      Planner    负责任务规划（拆解为 6 步标准流程）
      Executor   负责按规划逐步执行并回调进度
    """

    def __init__(self, on_step: Optional[Callable[[AgentStep], None]] = None):
        self.on_step = on_step
        self.planner = Planner()
        self.executor = Executor()

    def run(self, image_bytes: Optional[bytes], crop: str, growth_stage: str,
            soil_type: str, area: float, location: str,
            symptoms: str, enable_memory: bool = True) -> dict:

        plan: AgentPlan = self.planner.plan(
            image_bytes=image_bytes,
            crop=crop, growth_stage=growth_stage,
            soil_type=soil_type, area=area,
            location=location, symptoms=symptoms,
        )

        def _emit(step: AgentStep) -> None:
            if self.on_step is not None:
                try:
                    self.on_step(step)
                except Exception:
                    pass

        return self.executor.execute(
            plan=plan,
            image_bytes=image_bytes,
            crop=crop, growth_stage=growth_stage,
            soil_type=soil_type, area=area,
            location=location, symptoms=symptoms,
            enable_memory=enable_memory,
            on_step=_emit,
        )


__all__ = [
    "AgriAgent",
    "Planner",
    "Executor",
    "AgentPlan",
    "AgentStep",
    "KnowledgeService",
    "MemoryService",
    "SafetyService",
    "ReviewResult",
]
