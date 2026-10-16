from __future__ import annotations

from memory import history as _memory


class MemoryService:
    """
    Agent 封装层：地块历史记忆服务。
    底层复用 memory.history 模块（JSON 文件持久化）。
    """

    def record_visit(self, location: str, crop: str, growth_stage: str, area: float,
                     diagnosis: str, recommendation: str, note: str = "",
                     risk_level: str = "", content: str = "") -> dict:
        return _memory.record_visit(
            location=location, crop=crop, growth_stage=growth_stage,
            area=area, diagnosis=diagnosis, recommendation=recommendation,
            note=note, risk_level=risk_level, content=content,
        )

    def get_history(self, location: str, crop: str, area: float, limit: int = 5) -> list[dict]:
        return _memory.get_history(location, crop, area, limit=limit)

    def get_recent_all(self, limit: int = 10) -> list[dict]:
        return _memory.get_recent_all(limit=limit)

    def summarize_history(self, location: str, crop: str, area: float) -> str:
        return _memory.summarize_history(location, crop, area)

    def stats(self) -> dict:
        return _memory.history_stats()

    def clear(self) -> None:
        _memory.clear_history()


__all__ = ["MemoryService"]
