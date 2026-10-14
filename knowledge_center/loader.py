"""
农业知识中心 · 数据加载器。

自动读取 knowledge_center/data/*.json，合并为统一知识库。
支持作物病害知识 + 农药安全规范两类数据。
同时提供 save/delete 写入能力（农技员知识管理使用）。

V1.0 结构升级：
- 加载时通过 schema.normalize_entry 做内存规范化（旧字段→新字段映射、
  id/category_code/source_status 补齐），不修改 data/*.json 原始文件
- 提供 get_knowledge_stats() 知识库统计
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from knowledge_center.schema import normalize_category, normalize_entry


DATA_DIR = Path(__file__).resolve().parent / "data"

_DISEASE_FILES = ["maize.json", "potato.json", "wheat.json"]
_PESTICIDE_FILES = ["pesticide.json"]


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return [data]
    except (json.JSONDecodeError, OSError):
        return []


def _crop_to_filename(crop: str) -> str:
    """作物名 → data/ 下的 JSON 文件名（覆盖北方大田主要作物）。

    新增作物时请同步 `tools/build_crop_data.py` 的 `_FILENAMES`，
    两者必须保持一致，否则农技员端新增/编辑知识会写错文件。
    """
    name_map = {
        # 原有 8 种
        "玉米": "maize.json",
        "小麦": "wheat.json",
        "马铃薯": "potato.json",
        "大豆": "soybean.json",
        "棉花": "cotton.json",
        "花生": "peanut.json",
        "高粱": "sorghum.json",
        "向日葵": "sunflower.json",
        # 新增：北方主要大田作物
        "水稻": "rice.json",
        "谷子": "millet.json",
        "糜子": "broomcorn.json",
        "燕麦": "oats.json",
        "荞麦": "buckwheat.json",
        "大麦": "barley.json",
        "甜菜": "sugarbeet.json",
        "油菜": "rapeseed.json",
        "芝麻": "sesame.json",
        "亚麻": "flax.json",
        "绿豆": "mungbean.json",
        "豌豆": "pea.json",
        "蚕豆": "faba_bean.json",
        "红小豆": "adzuki.json",
        "苜蓿": "alfalfa.json",
        "蓖麻": "castor.json",
        "其他": "other.json",
    }
    fname = name_map.get(crop)
    if fname:
        return fname
    safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", crop).strip("_")
    if not safe:
        safe = "crop"
    return f"{safe}.json"


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_diseases() -> list[dict]:
    """加载全部作物病害知识条目（加载时内存规范化，不改原始文件）。

    跳过两个农药类文件：pesticide.json（人工核验条目）与
    pesticide_registry.json（公告批量导入）。否则登记库的上千个产品会被
    当成"病害条目"参与检索与统计（实测会污染知识库测试与检索评分）。
    """
    _SKIP = {"pesticide.json", "pesticide_registry.json"}
    out: list[dict] = []
    for fname in sorted(DATA_DIR.glob("*.json")):
        if fname.name in _SKIP:
            continue
        for entry in _load_json(fname):
            entry.setdefault("_source_file", fname.name)
            out.append(normalize_entry(entry))
    return out


def load_pesticides() -> list[dict]:
    """加载农药类别与安全规范（用于 Agent 安全审核增强）。

    原 category 中文值（杀菌剂/杀虫剂等）原样保留，仅增量补齐
    id/category_code/source_status 等规范化字段。
    """
    out: list[dict] = []
    path = DATA_DIR / "pesticide.json"
    for entry in _load_json(path):
        entry.setdefault("_source_file", path.name)
        out.append(normalize_entry(entry))
    return out


def load_registry_products() -> list[dict]:
    """加载机器导入的批量农药登记库（官方公告附件）。

    与 `load_pesticides()` 的分工：
      - `pesticide.json`：人工逐条核验的小型权威条目，含剂量/安全间隔期/来源
      - `pesticide_registry.json`：官方公告附件批量导入，只含作物与防治对象，
        用于「该药剂是否登记于本作物 + 本防治对象」的合规核验

    文件不存在时返回空列表，不影响既有功能。
    """
    path = DATA_DIR / "pesticide_registry.json"
    data = _load_json(path)
    # 注意 `_load_json` 会把顶层 dict 包成单元素列表，
    # 因此这里必须同时处理 [{"products": [...]}] 这种形态。
    items: list = []
    if isinstance(data, dict):
        items = data.get("products") or []
    else:
        for item in data or []:
            if isinstance(item, dict) and "products" in item and "name" not in item:
                items.extend(item.get("products") or [])
            else:
                items.append(item)

    out: list[dict] = []
    for p in items:
        if isinstance(p, dict) and str(p.get("name") or "").strip():
            out.append(p)
    return out


def load_knowledge() -> list[dict]:
    """返回全部农业知识条目（病害 + 农药安全）。"""
    return load_diseases() + load_pesticides()


def list_crops() -> list[str]:
    """返回知识库覆盖的作物种类列表。"""
    crops = set()
    for entry in load_diseases():
        c = entry.get("crop", "")
        if c:
            crops.add(c)
    return sorted(crops)


def list_diseases_by_crop(crop: str) -> list[dict]:
    """查询指定作物的全部病害条目。"""
    return [e for e in load_diseases() if e.get("crop") == crop]


def get_knowledge_stats() -> dict:
    """知识库统计（供管理页面 / 报告导出使用）。

    返回：
        {
            "total": 总条目数,
            "by_crop": {作物: 数量}（无 crop 的农药安全条目计入 "通用"）,
            "by_category": {枚举类别: 数量},
            "with_source": 有来源条目数,
            "without_source": 无来源条目数,
        }
    """
    entries = load_knowledge()
    by_crop: dict[str, int] = {}
    by_category: dict[str, int] = {}
    with_source = 0
    for e in entries:
        crop = str(e.get("crop") or "").strip() or "通用"
        by_crop[crop] = by_crop.get(crop, 0) + 1

        cat = e.get("category_code") or normalize_category(e.get("category")) or "other"
        by_category[cat] = by_category.get(cat, 0) + 1

        if str(e.get("source") or "").strip():
            with_source += 1
    return {
        "total": len(entries),
        "by_crop": by_crop,
        "by_category": by_category,
        "with_source": with_source,
        "without_source": len(entries) - with_source,
    }


# =========================================================================
# 写操作：农技员知识管理使用
# =========================================================================

def save_disease(entry: dict) -> tuple[bool, str]:
    """
    新增或更新一条病害知识。

    - 按 crop 定位到 data/{crop_filename}.json
    - 如果同 crop + disease 已存在 → 更新该条目
    - 否则 → 追加新条目

    返回 (成功标志, 消息)。
    """
    try:
        _ensure_dir()

        crop = entry.get("crop", "").strip()
        disease = entry.get("disease", "").strip()
        if not crop or not disease:
            return False, "crop 与 disease 字段不能为空"

        fname = _crop_to_filename(crop)
        path = DATA_DIR / fname

        existing = _load_json(path)
        replaced = False
        for i, e in enumerate(existing):
            if e.get("crop") == crop and e.get("disease") == disease:
                existing[i] = {**e, **entry}
                replaced = True
                break

        if not replaced:
            existing.append(entry)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        action = "更新" if replaced else "新增"
        return True, f"{action}成功 → {crop} / {disease} （{fname}）"
    except Exception as exc:
        return False, f"保存失败：{exc}"


def delete_disease(crop: str, disease: str) -> tuple[bool, str]:
    """删除指定作物下的指定病害条目。"""
    try:
        _ensure_dir()
        fname = _crop_to_filename(crop)
        path = DATA_DIR / fname
        existing = _load_json(path)
        new = [e for e in existing if not (e.get("crop") == crop and e.get("disease") == disease)]
        if len(new) == len(existing):
            return False, "未找到匹配条目"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
        return True, f"已删除 {crop} / {disease} （{fname}）"
    except Exception as exc:
        return False, f"删除失败：{exc}"


__all__ = [
    "load_knowledge",
    "load_diseases",
    "load_pesticides",
    "load_registry_products",
    "list_crops",
    "list_diseases_by_crop",
    "get_knowledge_stats",
    "save_disease",
    "delete_disease",
    "DATA_DIR",
]
