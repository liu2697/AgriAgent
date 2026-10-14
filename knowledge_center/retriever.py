"""
农业知识中心 · 检索器。

采用**关键词加权打分**检索（初版不使用向量数据库）。
评分维度（V1.0 结构升级后）：
  1. 作物精确匹配       +10
  2. 作物子串匹配        +5
  3. 病害名称精确匹配   +20   （最高权重）
  4. 病害别名匹配       +15   （高权重）
  5. 病害名称部分匹配    +8
  6. 症状关键词匹配     每个 +3（中等权重）
  7. 生育期匹配         每个 +3（中等权重）
  8. 关键词字段匹配     每个 +3（中等权重）
  9. 发生/有利条件匹配  每个 +2
 10. 风险因素匹配       每个 +2
 11. 诊断特征匹配       每个 +2
 12. 防治措施匹配       每个 +2（较低权重）
 13. 化学防治药剂匹配   每个 +1（较低权重）

候选集：全部知识条目（病害 + 农药安全）。
V1.1 起新增两道准入闸门（解决"仅作物命中 → 退化取文件前 3 条"的问题）：
  1. 内容证据：除作物外必须命中至少一个实质字段（病名/别名/症状/生育期/
     关键词/发生条件/诊断特征/防治/药剂）；
  2. 最低分 `_MIN_SCORE = 13`。
两闸门均不通过时返回空列表，上层应如实说明"未命中知识库"。
各字段内部改为饱和累加（命中数 n → 收敛到 step × n/(n+weight)），
使"命中更多症状"能加分，同时不让长描述把分数推向失控。
"""
from __future__ import annotations

import re
from typing import Optional

from knowledge_center.loader import load_knowledge
from knowledge_center.schema import normalize_category

# 最低准入分：仅作物命中（+5/+10）而症状/诊断特征零命中的条目不得进入候选集。
# 这类条目没有证据支撑，只是"该作物的第 N 条"，把它当作"检索命中"注入
# Prompt 并展示为"诊断依据"会误导农户。
_MIN_SCORE = 13

# 内容证据闸门只适用于「有症状语义」的条目（病害/虫害/草害/营养/水分/栽培）。
# 农药安全类条目按结构就没有 symptoms（内容在 products / forbidden_substances /
# safety_notes 里），对它们套用症状证据闸门会把「2甲4氯钠」这类查询直接误杀。
_EVIDENCE_GATED_CATEGORIES = {
    "disease", "pest", "weed", "nutrition", "water_management", "cultivation",
}

# 农药安全类条目只在查询确实涉及药剂/安全时才参与召回。
# 否则「玉米 大斑病」这类病害查询会把「杀菌剂」总览条目一并召回 ——
# 它既没有症状也没有病名，混进"诊断依据"只会干扰农户阅读。
_PESTICIDE_QUERY_HINTS = (
    "药", "剂", "杀菌", "杀虫", "除草", "农药", "禁限用", "残留", "间隔期",
    "安全用药", "配药", "打药", "喷施", "施用",
)


# 作物别名统一由 knowledge_center.crop_aliases 提供（单一数据源），
# 本文件不再单独维护 —— 两处维护必然不一致。


def _ngrams(text: str, n: int) -> list[str]:
    """从连续中文片段中提取字符 n-gram，供检索打分使用。"""
    if len(text) < n:
        return []
    return [text[i:i + n] for i in range(len(text) - n + 1)]


def _tokenize(text: str) -> list[str]:
    """中文友好分词：标点/空格切分后取 2-gram（辅以长片段精确短语）。

    为什么需要 n-gram：真实农户描述是连写中文（如「叶片出现褐色长条斑」），
    按标点切分后整句变成一个 token，无法命中知识库里「褐色长条斑」「长条斑」
    等短语，导致检索退化为「按文件顺序取该作物前 3 条」。

    为什么以 2-gram 为主、不再计入长片段：
    `_coverage_score` 用 hits/token数 表示"查询有多少被解释"，若把「植株矮化」
    整段和它的 2-gram 一起计入，同一概念被算了 4 次，覆盖率反而被稀释，
    真正逐字命中「矮化」的条目会卡在准入线下（实测 12.33 < 13）。
    中文症状词以二字为主，2-gram 计数最贴近"命中了几个症状词"的直觉。

    保留 3-gram 仅用于 ≥5 字的片段，帮助长句精确短语（如「叶片出现褐色」）
    获得更强的相似度信号。
    """
    if not text:
        return []

    parts = [p for p in re.split(r"[\s,，。.;；、!?！？\-_\(\)\[\]{}<>《》\"'`]+", text.lower()) if p]

    tokens: list[str] = []
    for part in parts:
        if len(part) >= 2:
            tokens.extend(_ngrams(part, 2))
        if len(part) >= 5:
            tokens.extend(_ngrams(part, 3))

    # 去重但保留顺序
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if len(t) >= 2 and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _expand_crop(crop_hint: str) -> list[str]:
    """将作物提示扩展为可能匹配的关键词列表。

    别名数据统一取 `knowledge_center.crop_aliases.CROP_ALIASES`：
    农户可能直接写俗称（「土豆」「苞米」「谷子/小米」），先解析为规范名，
    再把该作物的全部别名纳入匹配，作物硬过滤才不会误杀。
    """
    if not crop_hint:
        return []

    from knowledge_center.crop_aliases import CROP_ALIASES, resolve_crop

    expanded: list[str] = [crop_hint]
    canon = resolve_crop(crop_hint)
    if canon:
        expanded.append(canon)
        expanded.extend(CROP_ALIASES.get(canon, []))
    if crop_hint in CROP_ALIASES:
        expanded.extend(CROP_ALIASES[crop_hint])
    return list({k for k in expanded if k})


def _match(text: str, tokens: list[str]) -> int:
    """返回命中该字段的不同 token 数量。"""
    if not text:
        return 0
    t = str(text).lower()
    seen: set[str] = set()
    for tok in tokens:
        if tok and tok not in seen and tok in t:
            seen.add(tok)
    return len(seen)


def _coverage_score(score: float, hits: int, n_tokens: int, cap: float) -> float:
    """按「查询覆盖率」而非「命中个数」累加。

    hits / n_tokens 表示"查询里有多大比例的词命中了本字段"：
      - 农户描述与知识库典型症状写法逐字一致 → 覆盖率≈1 → 得满 cap
      - 仅命中「褐色」「叶片」等通用词       → 覆盖率低 → 按比例得部分分
    这解决了纯 n-gram 计数的一个致命问题：通用植保词汇（叶片/病斑/褐色）
    会同时命中几乎全部条目，把分数挤在窄区间里失去区分度，
    反而让"逐字匹配整句症状"的条目排不到第一。

    注意必须是**线性**的 min(1, hits/n)，不能放大系数后再截断：
    曾用 min(1, 2*hits/n)，结果"16/16 全命中"与"9/16 命中"都被截断到
    1.0 而得分相同，区分度再次丢失（玉米大斑病被玉米小斑病压过）。
    """
    if hits <= 0 or n_tokens <= 0:
        return score
    ratio = min(1.0, hits / n_tokens)
    return score + cap * ratio


def _accumulate_evidence(entry: dict, tokens: list[str]) -> bool:
    """除作物外是否命中任何实质内容字段（只用于准入判断，不计分）。"""
    if not tokens:
        return False

    texts: list[str] = []
    for key in ("disease", "prevention", "control_measures", "chemical_control",
                "category", "safety_notes", "safety_principles", "data_note"):
        if entry.get(key):
            texts.append(str(entry[key]))
    for key in ("symptoms", "growth_stage", "keywords", "favorable_conditions",
                "occurrence_conditions", "risk_factors", "diagnosis_features", "aliases"):
        texts.extend(str(v) for v in (entry.get(key) or []))
    for prod in (entry.get("products", []) or []):
        if isinstance(prod, dict):
            texts.append(str(prod.get("name") or ""))
            texts.extend(str(t) for t in (prod.get("registered_targets") or []))
            texts.extend(str(t) for t in (prod.get("crops") or []))
    for f in (entry.get("forbidden_substances", []) or []):
        if isinstance(f, dict):
            texts.append(str(f.get("name") or ""))
            texts.extend(str(r) for r in (f.get("reasons") or []))

    text = " ".join(texts).lower()
    return any(t in text for t in tokens)


def _score_entry(entry: dict, query_tokens: list[str],
                 crop_expanded: list[str], query_text: str = "") -> float:
    """给单条知识条目打分（返回分数；准入判断另见 _accumulate_evidence）。

    打分维度与权重沿用 V1.0 设计：病害名 +20 > 别名 +15 > 病害名部分 +8
    > 作物 +10/+5 > 症状 > 诊断特征/关键词/生育期/发生条件 > 防治 > 药剂。

    各字段按「查询覆盖率」而非「命中个数」计分上限：
    命中数会同时被"命中的通用词数量"和"查询长度"影响，而覆盖率表达的是
    "农户描述有多大比例被这条知识解释"，更接近诊断语义。
    """
    score = 0.0

    # 作物词不参与内容维度打分：keywords / disease 是由含作物名的字段派生的
    # （如「玉米大斑病」→ keywords 含「玉米」），若不过滤，只输入作物名
    # （query="玉米"）就会靠内容维度凑够最低分，让整份作物病害清单都变成
    # "检索命中"。作物匹配本身已由下面的作物维度单独计分。
    crop_tokens = {str(entry.get("crop") or "").lower()}
    crop_tokens.update(str(c).lower() for c in crop_expanded)
    tokens = [t for t in query_tokens if t and t not in crop_tokens]
    n_tok = len(tokens)

    # --- 作物匹配 ---
    entry_crop = (entry.get("crop") or "").lower()
    for kw in crop_expanded:
        kl = kw.lower()
        if kl and entry_crop == kl:
            score += 10
        elif kl and kl in entry_crop:
            score += 5

    # --- 病害名称 / 别名匹配（最高权重，决定性信号） ---
    disease = (entry.get("disease") or "").lower()
    alias_list = [str(a).lower() for a in (entry.get("aliases", []) or [])]
    disease_text = f"{disease} {' '.join(alias_list)}".strip()
    for tok in tokens:
        if tok == disease and disease:
            score += 20
        elif tok in alias_list:
            score += 15
        elif len(tok) >= 3 and tok in disease_text:
            score += 8

    # --- 条目自身身份命中（确定性证据，不按覆盖率打折） ---
    # 查询里直接出现条目的名称（如「杀菌剂」「2甲4氯钠」「玉米大斑病」）属于
    # 精确指名，与"症状描述有多像"是两类证据：后者该按覆盖率打分，前者只要
    # 命中就该给足以过闸门的分数。若也按覆盖率打折，条目名只占长查询的一小
    # 部分，就会被 _MIN_SCORE 误杀（曾导致「杀菌剂 科学安全用药」返回空）。
    # 用 query 原文匹配（而非 token 拼串）：tokenizer 只产出 2-gram，
    # 「杀菌剂」这类 3 字分类名在 token 里已不存在，必须比对原文。
    raw = (query_text or "").lower()
    identity_names = [entry.get("category"), entry.get("disease")]
    for a in (entry.get("aliases", []) or []):
        identity_names.append(a)
    for prod in (entry.get("products", []) or []):
        if isinstance(prod, dict):
            identity_names.append(prod.get("name"))
    for f in (entry.get("forbidden_substances", []) or []):
        if isinstance(f, dict):
            identity_names.append(f.get("name"))
    for name in identity_names:
        nm = str(name or "").strip().lower()
        if len(nm) >= 3 and nm in raw:
            score += 15
            break

    # --- 症状（主证据） ---
    # 权重高于诊断特征/关键词：诊断特征里常含「褐色」「叶片」这类通用词，
    # 若与症状同权，会抵消"逐字命中典型症状"这一最可靠信号
    # （曾导致「叶片出现褐色长条斑」把玉米小斑病排到玉米大斑病之前）。
    n = _match(" ".join(str(s) for s in (entry.get("symptoms", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 14.0)

    # --- 诊断特征（辅助证据，权重需低于症状） ---
    n = _match(" ".join(str(f) for f in (entry.get("diagnosis_features", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 8.0)

    # --- 关键词字段（派生自病名/别名/作物，辅助权重） ---
    n = _match(" ".join(str(k) for k in (entry.get("keywords", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 6.0)

    # --- 生育期 ---
    n = _match(" ".join(str(s) for s in (entry.get("growth_stage", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 6.0)

    # --- 发生 / 有利条件（新字段优先，旧字段兼容回退，避免重复计分） ---
    conditions = entry.get("favorable_conditions") or entry.get("occurrence_conditions") or []
    n = _match(" ".join(str(c) for c in conditions), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 5.0)

    # --- 风险因素 ---
    n = _match(" ".join(str(r) for r in (entry.get("risk_factors", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 4.0)

    # --- 防治措施（较低权重） ---
    n = _match(" ".join(str(p) for p in (entry.get("prevention", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 4.0)

    n = _match(" ".join(str(c) for c in (entry.get("control_measures", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 4.0)

    # --- 化学防治药剂（较低权重） ---
    n = _match(" ".join(str(c) for c in (entry.get("chemical_control", []) or [])), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 3.0)

    # --- 农药安全条目专有字段：分类名 / 产品名 / 登记靶标 / 安全要点 / 禁限用物质 ---
    # 这类条目没有 symptoms、crop 也常为空，内容都在这些字段里
    # （category=「杀菌剂」、safety_notes=「…科学安全用药…」等），
    # 若不单独计分，「2甲4氯钠」「杀菌剂 科学安全用药」这类查询会被准入闸门误杀。
    safety_texts = [str(entry.get("category") or ""), str(entry.get("disease") or "")]
    safety_texts.extend(str(k) for k in (entry.get("keywords") or []))
    safety_texts.extend(str(s) for s in (entry.get("safety_notes") or []))
    safety_texts.extend(str(s) for s in (entry.get("safety_principles") or []))
    safety_texts.extend(str(s) for s in (entry.get("data_note") or []))
    for prod in (entry.get("products", []) or []):
        if isinstance(prod, dict):
            safety_texts.append(str(prod.get("name") or ""))
            safety_texts.extend(str(t) for t in (prod.get("registered_targets") or []))
            safety_texts.extend(str(t) for t in (prod.get("crops") or []))
    for f in (entry.get("forbidden_substances", []) or []):
        if isinstance(f, dict):
            safety_texts.append(str(f.get("name") or ""))
            safety_texts.extend(str(r) for r in (f.get("reasons") or []))
    n = _match(" ".join(safety_texts), tokens)
    if n:
        score = _coverage_score(score, n, n_tok, 10.0)

    return round(score, 2)


def search(query: str, crop_hint: Optional[str] = None, top_k: int = 3) -> list[dict]:
    """
    农业知识检索主入口。

    参数：
        query: 农户描述 / 诊断 Prompt
        crop_hint: 作物提示（如 "玉米"），用于加分
        top_k: 返回前 K 条

    返回：
        [
            {
                "disease": "玉米大斑病",
                "crop": "玉米",
                "score": 38.5,
                "relevance_score": 38.5,          # 兼容旧 knowledge.base 返回格式
                "knowledge": { 完整知识条目 dict },
                "symptoms": [...],                 # 兼容旧格式
                "registered_pesticides": [...],    # 兼容旧格式
                ...                               # 其他原始字段
            },
            ...
        ]
    """
    query_tokens = _tokenize(query)
    crop_expanded = _expand_crop(crop_hint or "")

    candidates = load_knowledge()

    # 农药安全类条目只在查询确实涉及药剂/安全时才参与召回，
    # 避免「玉米 大斑病」这类病害查询把「杀菌剂」总览条目混进"诊断依据"。
    # 判定同时看两类线索：关键词（药/剂/残留…）与条目自身的分类名
    # （杀菌剂 / 杀虫剂 / 除草剂 / 禁限用农药提示）。后者从数据里取，
    # 新增农药分类时无需再改这里。
    query_raw = str(query or "")
    pesticide_names = set()
    for e in candidates:
        if (e.get("category_code") or normalize_category(e.get("category"))) != "pesticide_safety":
            continue
        pesticide_names.add(str(e.get("category") or "").strip())
        for prod in (e.get("products", []) or []):
            if isinstance(prod, dict):
                pesticide_names.add(str(prod.get("name") or "").strip())
        for f in (e.get("forbidden_substances", []) or []):
            if isinstance(f, dict):
                pesticide_names.add(str(f.get("name") or "").strip())
    allow_pesticide = (
        any(h in query_raw for h in _PESTICIDE_QUERY_HINTS)
        or any(nm and nm in query_raw for nm in pesticide_names)
    )

    scored = []
    for entry in candidates:
        # 作物硬过滤：指定了作物时，不得返回其他作物的条目。
        # 否则「叶片卷曲」这类通用症状会把玉米蚜虫推给马铃薯农户，
        # 而农户看到的将是"别的作物的病害"，属于硬伤。
        # 例外：条目自身没有 crop（农药安全类总览）时不做过滤。
        # 若 crop_hint 本身不在知识库覆盖范围内（如「其他」），crop_expanded
        # 为空，此时也不过滤。
        if crop_expanded:
            entry_crop = str(entry.get("crop") or "").lower()
            if entry_crop and not any(k.lower() in entry_crop for k in crop_expanded):
                continue

        s = _score_entry(entry, query_tokens, crop_expanded, query_text=str(query or ""))
        # 双闸门：达到最低分，且（对有症状语义的条目）命中了实质内容字段。
        # 闸门导致空结果时返回空列表 —— 上层据此如实说明"未命中知识库"，
        # 而不是把该作物的前 N 条当成"检索结果"注入 Prompt 并展示给农户。
        if s < _MIN_SCORE:
            continue
        cat = entry.get("category_code") or normalize_category(entry.get("category"))
        if cat == "pesticide_safety" and not allow_pesticide:
            continue
        if cat in _EVIDENCE_GATED_CATEGORIES:
            crop_tokens = {str(entry.get("crop") or "").lower()}
            crop_tokens.update(str(c).lower() for c in crop_expanded)
            tokens = [t for t in query_tokens if t and t not in crop_tokens]
            if not _accumulate_evidence(entry, tokens):
                continue
        result = {
            "disease": entry.get("disease", "") or entry.get("category", ""),
            "crop": entry.get("crop", ""),
            "score": round(s, 2),
            "relevance_score": round(s, 2),
            "knowledge": entry,
            "symptoms": entry.get("symptoms", []),
            "registered_pesticides": (
                (entry.get("pesticide_reference") or {}).get("registered", [])
            ),
            "aliases": entry.get("aliases", []),
            "occurrence_conditions": entry.get("occurrence_conditions", []),
            "prevention": entry.get("prevention", []),
            "diagnosis_features": entry.get("diagnosis_features", []),
            "risk_level": entry.get("risk_level", ""),
            # V1.0 结构升级新增（增量字段，不影响旧调用方）
            "category": entry.get("category", ""),
            "category_code": entry.get("category_code", ""),
            "source_status": entry.get("source_status", ""),
        }
        scored.append(result)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


__all__ = ["search"]
