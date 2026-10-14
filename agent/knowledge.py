"""
Agent 封装层：农业知识库检索服务。

底层实现：优先使用 knowledge_center.retriever（结构化农业知识中心 RAG），
加载失败时自动回退到 knowledge.base（原硬编码关键词知识库）。

调用接口：KnowledgeService.search(query, crop_hint=None, top_k=3)
          返回格式与 knowledge.base.search_knowledge 保持完全一致，
          因此 agent/executor.py 等上层调用方无需修改。
"""
from __future__ import annotations

from typing import Optional, List, Dict


class KnowledgeService:
    """
    Agent 封装层：农业知识检索服务。
    """

    def __init__(self):
        self._impl = self._load_impl()

    @staticmethod
    def _load_impl():
        """优先加载 knowledge_center，失败回退 knowledge.base。"""
        try:
            from knowledge_center.retriever import search as _kc_search
            from knowledge_center.loader import load_diseases
            diseases = load_diseases()
            if diseases:
                return _kc_search
        except Exception:
            pass

        try:
            from knowledge.base import search_knowledge as _legacy_search
            return _legacy_search
        except Exception:
            return lambda q, crop_hint=None, top_k=3: []

    def search(self, query: str, crop_hint: Optional[str] = None, top_k: int = 3) -> list[dict]:
        """
        检索农业知识库，返回 Top-K 命中条目。

        返回格式与 knowledge.base.search_knowledge 保持一致：
        [
            {
                "disease": str,
                "crop": str,
                "relevance_score": float,
                "symptoms": list[str],
                "registered_pesticides": list[str],
                "score": float,                    # knowledge_center 新增
                "knowledge": dict,                 # knowledge_center 新增（完整条目）
                ...                                # 其他原始字段
            },
            ...
        ]
        """
        return self._impl(query, crop_hint=crop_hint, top_k=top_k)

    def dump(self) -> str:
        from knowledge.base import dump_knowledge
        return dump_knowledge()

    @property
    def source(self) -> str:
        try:
            from knowledge_center.loader import load_diseases
            diseases = load_diseases()
            crops = sorted({d.get("crop", "") for d in diseases if d.get("crop")})
            return f"农业知识中心 v2.0（{len(diseases)} 条病害 · {', '.join(crops)}）"
        except Exception:
            return "内置农业知识库 v1.0（回退模式）"


__all__ = ["KnowledgeService"]
