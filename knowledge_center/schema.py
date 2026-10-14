"""
农业知识中心 · 统一知识条目 Schema（V1.0 结构升级）。

设计原则：
- 覆盖北方大田 9 种作物（玉米/小麦/马铃薯/大豆/棉花/花生/高粱/向日葵/其他）
  + 独立的农药安全知识
- 向后兼容：旧条目（无 id/category/source）在**加载时内存规范化**补齐新字段，
  绝不修改 data/*.json 原始文件
- 纯结构模块：只做字段定义与旧→新字段映射，不生成任何农业事实
"""
from __future__ import annotations

import hashlib
from typing import Any

# ---------------------------------------------------------------------------
# category 枚举（存储值）与中文展示名
# ---------------------------------------------------------------------------
CATEGORIES: list[str] = [
    "disease",           # 病害
    "pest",              # 虫害
    "weed",              # 草害
    "nutrition",         # 营养管理
    "water_management",  # 水分管理
    "cultivation",       # 栽培管理
    "pesticide_safety",  # 农药安全
    "other",             # 其他
]

CATEGORY_LABELS: dict[str, str] = {
    "disease": "病害",
    "pest": "虫害",
    "weed": "草害",
    "nutrition": "营养管理",
    "water_management": "水分管理",
    "cultivation": "栽培管理",
    "pesticide_safety": "农药安全",
    "other": "其他",
}

# ---------------------------------------------------------------------------
# 病虫害风险等级枚举（与 diagnosis_records / Safety 的取值体系一致）
#   高 / 中 / 低 / 未知
# 说明：未知是合法值，表示现有来源不足以可靠确定风险等级，禁止为补齐
# 字段而凭空填写高/中/低。农药安全类条目无此语义，不做 risk_level 规范化。
# ---------------------------------------------------------------------------
RISK_LEVELS: list[str] = ["高", "中", "低", "未知"]

# 旧数据中的中文类别值 → 枚举（仅加载时内存映射，不改原文件）
_CATEGORY_ALIASES: dict[str, str] = {
    "病害": "disease",
    "虫害": "pest",
    "草害": "weed",
    "营养": "nutrition",
    "施肥": "nutrition",
    "水分管理": "water_management",
    "灌溉": "water_management",
    "栽培": "cultivation",
    "栽培管理": "cultivation",
    "农药安全": "pesticide_safety",
    "农药": "pesticide_safety",
    "杀菌剂": "pesticide_safety",
    "杀虫剂": "pesticide_safety",
    "除草剂": "pesticide_safety",
    "植物生长调节剂": "pesticide_safety",
    "禁限用农药提示": "pesticide_safety",
    "其他": "other",
}

# 统一 Schema 全部字段（validator / 文档 / 后续管理页使用）
SCHEMA_FIELDS: list[str] = [
    "id", "crop", "category", "disease", "risk_level", "aliases", "growth_stage",
    "symptoms", "favorable_conditions", "risk_factors", "prevention",
    "control_measures", "chemical_control", "safety_notes", "keywords",
    "region", "source", "source_title", "source_date", "source_url",
]

LIST_FIELDS: list[str] = [
    "aliases", "growth_stage", "symptoms", "favorable_conditions",
    "risk_factors", "prevention", "control_measures", "chemical_control",
    "safety_notes", "keywords", "region",
]


def normalize_category(raw: Any) -> str:
    """任意类别值 → 枚举值；无法映射返回空字符串。"""
    if raw is None:
        return ""
    raw = str(raw).strip()
    if not raw:
        return ""
    if raw in CATEGORIES:
        return raw
    return _CATEGORY_ALIASES.get(raw, "")


def as_list(value: Any) -> list:
    """把任意值安全转为 list（str → [str]，None → []）。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def _make_id(entry: dict) -> str:
    """按内容生成确定性 id（同一条目多次加载 id 稳定）。"""
    basis = "|".join([
        str(entry.get("crop", "")),
        str(entry.get("disease", "")),
        str(entry.get("category", "")),
        str(entry.get("_source_file", "")),
    ])
    return "KB-" + hashlib.md5(basis.encode("utf-8")).hexdigest()[:8]


def _derive_keywords(entry: dict) -> list[str]:
    """从条目既有字段生成检索关键词索引。

    仅重组已有内容（病害名/别名/作物/农药类别/药剂名/登记靶标），
    不新增、不编造任何农业事实。
    """
    kws: list[str] = []
    for v in (entry.get("disease"), entry.get("crop")):
        if v:
            kws.append(str(v))
    kws.extend(str(a) for a in as_list(entry.get("aliases")))

    if normalize_category(entry.get("category")) == "pesticide_safety":
        if entry.get("category"):
            kws.append(str(entry["category"]))
        for prod in entry.get("products", []) or []:
            if isinstance(prod, dict):
                if prod.get("name"):
                    kws.append(str(prod["name"]))
                kws.extend(str(t) for t in as_list(prod.get("registered_targets")))
        for f in entry.get("forbidden_substances", []) or []:
            if isinstance(f, dict) and f.get("name"):
                kws.append(str(f["name"]))

    seen: set[str] = set()
    out: list[str] = []
    for k in kws:
        k = k.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def normalize_entry(entry: dict) -> dict:
    """将任意知识条目规范化为统一 Schema（纯内存增量操作，不改原文件）。

    兼容映射（旧字段全部保留原样，同时补齐新字段）：
      occurrence_conditions          → favorable_conditions（复制）
      pesticide_reference.registered → chemical_control（复制）
      prevention 不复制到 control_measures（二者语义不同，由新数据显式填写）

    其他规则：
      - id 缺失时按内容生成确定性 id（KB-xxxxxxxx）
      - category 缺失时按来源补默认值；中文旧值原样保留并生成
        category_code（枚举）与 category_label（中文展示名）
      - keywords 缺失时由既有字段派生
      - source 为空 → source_status = "unverified"
      - region 为可选字段：有则保留，无则不添加（不虚构区域结论）
    """
    if not isinstance(entry, dict):
        return entry
    e = dict(entry)  # 浅拷贝，绝不改动调用方与磁盘上的原始数据

    # --- id ---
    if not str(e.get("id") or "").strip():
        e["id"] = _make_id(e)

    # --- category / category_code / category_label ---
    if not str(e.get("category") or "").strip():
        # 旧条目无 category：病害文件默认 disease，农药文件默认 pesticide_safety
        default_cat = ("pesticide_safety"
                       if e.get("_source_file") == "pesticide.json" else "disease")
        e["category"] = default_cat
    cat_code = normalize_category(e.get("category"))
    if not cat_code and e.get("_source_file") == "pesticide.json":
        cat_code = "pesticide_safety"
    if not cat_code:
        cat_code = "other"
    e["category_code"] = cat_code
    e["category_label"] = CATEGORY_LABELS.get(e["category"], e["category"])

    # --- risk_level：仅病害/虫害条目规范化（农药安全类无此语义，不处理） ---
    # 合法值原样保留；缺失或非法值统一记为"未知"，保证下游永不遇到
    # null / 空串 / 非法枚举（P2-3：打通 unknown 状态）
    if cat_code != "pesticide_safety":
        risk = str(e.get("risk_level") or "").strip()
        e["risk_level"] = risk if risk in RISK_LEVELS else "未知"

    # --- 新字段补齐（仅缺失时生成，不覆盖已有值） ---
    if not as_list(e.get("favorable_conditions")) and as_list(e.get("occurrence_conditions")):
        e["favorable_conditions"] = list(as_list(e["occurrence_conditions"]))

    if not as_list(e.get("chemical_control")):
        pr = e.get("pesticide_reference")
        if isinstance(pr, dict) and as_list(pr.get("registered")):
            e["chemical_control"] = list(as_list(pr["registered"]))

    if not as_list(e.get("keywords")):
        e["keywords"] = _derive_keywords(e)

    # --- 来源与可信度（来源字段只做溯源，不虚构） ---
    e["source_status"] = "verified" if str(e.get("source") or "").strip() else "unverified"

    # --- region：可选字段，有则规范为 list ---
    if "region" in e:
        e["region"] = as_list(e["region"])

    return e


__all__ = [
    "CATEGORIES",
    "CATEGORY_LABELS",
    "SCHEMA_FIELDS",
    "LIST_FIELDS",
    "normalize_category",
    "as_list",
    "normalize_entry",
]
