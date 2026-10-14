# 农业知识中心（Knowledge Center）

为农智链 AgriAgent 提供 **RAG（Retrieval-Augmented Generation）知识增强**能力，
替代原有 `knowledge/base.py` 中的硬编码病害知识。

## 设计目标

- **结构化存储**：每条知识包含作物、病害、别名、症状、发生条件、诊断特征、防治建议、农药参考、风险等级等字段
- **可扩展**：新增作物病害只需在 `data/` 下添加 JSON 文件，无需修改代码
- **初版轻量**：不依赖向量数据库，采用关键词加权打分检索
- **接口兼容**：`agent/knowledge.py` 对外接口保持不变，`agent/executor.py` / `agent/planner.py` 无需任何修改

## 目录结构

```
knowledge_center/
├── __init__.py          # 包导出（load_knowledge / search / ...）
├── loader.py            # 数据加载器（自动读取 data/*.json）
├── retriever.py         # 检索器（关键词加权打分）
├── README.md
└── data/
    ├── maize.json       # 玉米病害（大斑病 / 小斑病 / 锈病 / 蚜虫）
    ├── potato.json      # 马铃薯病害（晚疫病 / 早疫病）
    ├── wheat.json       # 小麦病害（条锈病 / 赤霉病）
    └── pesticide.json   # 农药安全规范（杀菌剂 / 杀虫剂 / 禁限用农药提示）
```

## 知识数据类型

| 类型 | 字段 | 示例 |
|------|------|------|
| **作物病害** | crop / disease / aliases / symptoms / occurrence_conditions / diagnosis_features / prevention / pesticide_reference / risk_level | 玉米 · 玉米大斑病 |
| **农药安全** | category / products[].{name, mode, registered_targets, dosage, safety_interval_days} | 杀菌剂 · 苯醚甲环唑 |
| **禁限用提示** | forbidden_substances / safety_principles | 百草枯 / 滴滴涕 |

## 使用方式

### 1. 直接调用检索器

```python
from knowledge_center.retriever import search

hits = search(
    query="叶片出现褐色长条斑",
    crop_hint="玉米",
    top_k=3,
)

for h in hits:
    print(h["disease"], h["score"], h["risk_level"])
    print(h["knowledge"]["symptoms"])
```

### 2. 通过 Agent 封装层（推荐）

```python
from agent.knowledge import KnowledgeService

ks = KnowledgeService()
print(ks.source)  # 农业知识中心 v2.0（8 条病害 · 玉米, 马铃薯, 小麦）

hits = ks.search("叶片水渍状病斑", crop_hint="马铃薯")
```

### 3. 数据管理

```python
from knowledge_center.loader import (
    load_knowledge,           # 全部知识（病害 + 农药）
    load_diseases,           # 仅病害
    load_pesticides,         # 仅农药安全规范
    list_crops,              # ["玉米", "马铃薯", "小麦"]
    list_diseases_by_crop,   # 返回指定作物病害列表
)
```

## 检索打分逻辑

采用 **关键词加权打分**（初版方案，后续可替换为向量数据库）：

| 维度 | 满分 | 说明 |
|------|------|------|
| 作物精确匹配 | +10 | `crop_hint` 与条目中 `crop` 完全一致 |
| 作物子串匹配 | +5 | 包含关系 |
| 病害名称精确匹配 | +20 | query 包含 disease 全名 |
| 病害别名匹配 | +15 | query 包含 aliases 中任一别名 |
| 症状关键词 | +3/词 | query 分词后命中 symptoms |
| 发生条件关键词 | +2/词 | 命中 occurrence_conditions |
| 诊断特征关键词 | +2/词 | 命中 diagnosis_features |

作物关键词别名表（retriever.py 中 `_CROP_KEYWORDS`）：
玉米 ↔ 玉米/玉蜀黍/棒子/苞谷 · 小麦 ↔ 小麦/麦 · 马铃薯 ↔ 马铃薯/土豆/洋山芋

## Agent 调用链变化

```
【改造前】
Executor → knowledge.base.search_knowledge(query, crop_hint, top_k)
                 │
                 └─ 硬编码 10 条病害字典，关键词 in 模糊匹配

【改造后】
Executor → agent.KnowledgeService.search(query, crop_hint, top_k)
                 │
                 ├─(优先) knowledge_center.retriever.search
                 │         │
                 │         └─ data/*.json 结构化读取 + 加权打分
                 │
                 └─(回退) knowledge.base.search_knowledge
                          （knowledge_center 加载失败时自动启用）
```

**Executor / Planner / Memory / Safety 全部不动**。只有 `agent/knowledge.py` 这一个文件做了底层实现替换。

## 如何扩展

新增一个作物病害：在 `knowledge_center/data/` 下新建 `{crop}.json`，格式参考 `maize.json`。Agent 下次启动时自动加载，无需修改任何代码。

```json
[
  {
    "crop": "水稻",
    "disease": "稻瘟病",
    "aliases": ["稻瘟"],
    "symptoms": [...],
    "occurrence_conditions": [...],
    "diagnosis_features": [...],
    "prevention": [...],
    "pesticide_reference": {...},
    "risk_level": "高"
  }
]
```

## 测试用例

```python
from knowledge_center.retriever import search

# 用例 1：玉米 → 大斑病
hits = search("玉米 叶片出现褐色长条斑", crop_hint="玉米", top_k=1)
assert hits[0]["disease"] == "玉米大斑病"

# 用例 2：马铃薯 → 晚疫病
hits = search("马铃薯 叶片水渍状病斑", crop_hint="马铃薯", top_k=1)
assert hits[0]["disease"] == "马铃薯晚疫病"

# 用例 3：小麦 → 赤霉病
hits = search("小麦 麦穗小穗颖壳变褐 粉红色霉层", crop_hint="小麦", top_k=1)
assert hits[0]["disease"] == "小麦赤霉病"

# 用例 4：小麦 → 条锈病
hits = search("小麦 叶片黄色斑点 沿叶脉纵向排列", crop_hint="小麦", top_k=1)
assert hits[0]["disease"] == "小麦条锈病"
```

## 后续规划

- [ ] 引入向量数据库（ChromaDB / FAISS），构建真正的语义检索
- [ ] 知识条目扩充：覆盖北方 15+ 主栽作物、50+ 病害
- [ ] 引入知识图谱（病害-作物-农药-风险 关联）
- [ ] LLM 生成答案中自动注入 Top-K 检索片段，提升可解释性
- [ ] 知识版本管理 + 更新日志
