"""
农户端症状标签（chips）。

设计原则：
1. **标签文案与知识库用词对齐**——每个 chip 的 `query` 必须包含知识库
   `symptoms` / `diagnosis_features` 里真实出现的短语，否则标签点了也检索不到。
   例如「褐色长条斑」对应玉米大斑病症状「叶片出现褐色长条斑」。
2. **不新增农业事实**——本模块只做"口语标签 → 知识库既有用词"的映射，
   不写任何诊断结论、不引入知识库里没有的病害描述。
3. **面向不识字/不便打字的农户**——用可选标签替代自由文本输入，
   选中项拼成检索 query 与 LLM 上下文，避免口语连写导致检索失效。

维护约定：修改 `query` 后请运行 `tests/test_knowledge.py`，
并抽查 `knowledge_center.retriever.search` 的命中结果是否仍然合理。
"""
from __future__ import annotations

# (标签文案, 检索用词)  — 检索用词取自知识库既有词汇
SYMPTOM_CHIPS: list[tuple[str, str]] = [
    ("斑点", "斑点"),
    ("长条斑", "长条斑"),
    ("梭形斑", "梭形"),
    ("圆形斑", "圆形病斑"),
    ("同心轮纹", "同心轮纹"),
    ("水渍纹", "水渍状"),
    ("长霉", "霉层"),
    ("粉状物", "黄色粉末"),
    ("叶片发黄", "叶片黄化"),
    ("叶片卷曲", "叶片卷曲"),
    ("植株矮小", "植株矮化"),
    ("萎蔫枯死", "叶片萎蔫"),
    ("有虫子", "虫体"),
    ("蛀孔虫粪", "蛀孔"),
    ("穗部异常", "籽粒干瘪"),
    ("根部变褐", "根部变褐"),
]

# 标签文案 → 检索用词
CHIP_QUERY: dict[str, str] = {label: q for label, q in SYMPTOM_CHIPS}

# 标签文案列表（供 UI 渲染）
CHIP_LABELS: list[str] = [label for label, _ in SYMPTOM_CHIPS]


def build_symptom_text(labels: list[str]) -> str:
    """把选中的症状标签拼成检索用文本（带去重，顺序稳定）。"""
    seen: set[str] = set()
    parts: list[str] = []
    for label in labels or []:
        q = CHIP_QUERY.get(label)
        if not q or q in seen:
            continue
        seen.add(q)
        parts.append(q)
    return "、".join(parts)


__all__ = ["SYMPTOM_CHIPS", "CHIP_QUERY", "CHIP_LABELS", "build_symptom_text"]
