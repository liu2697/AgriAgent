"""
农业知识中心（Knowledge Center）。

为农智链 AgriAgent 提供 RAG（Retrieval-Augmented Generation）知识增强能力，
替代原有 knowledge/base.py 中的硬编码病害知识。

使用方式：
    from knowledge_center.retriever import search
    hits = search(query="玉米 叶片出现褐色长条斑", crop_hint="玉米", top_k=3)
    for h in hits:
        print(h["disease"], h["score"])
"""
from knowledge_center.loader import (
    load_knowledge, load_diseases, load_pesticides,
    list_crops, list_diseases_by_crop,
    save_disease, delete_disease, DATA_DIR,
)
from knowledge_center.retriever import search

__all__ = [
    "load_knowledge",
    "load_diseases",
    "load_pesticides",
    "list_crops",
    "list_diseases_by_crop",
    "save_disease",
    "delete_disease",
    "DATA_DIR",
    "search",
]
