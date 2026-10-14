"""
农药登记数据导入器。

## 数据来源（官方、公开）

农业农村部农药管理司发布的《农药登记信息》公告，附件为官方 XLS。
链路（已验证可程序化获取）：

    中国农药信息网"登记信息发布"栏目
      → POST http://219.141.234.8/zgnyxxw/zwb/getPage  (id=753, 分页)
      → 公告详情页 /zwb/detail/{id}
      → 原文链接 https://zzys.moa.gov.cn/gzdt/...
      → 附件 P020xxxxxxxx.xls

官方 XLS 字段（一期一表，实测表头一致）：

    序号 | 登记证号 | 登记证持有人 | 农药名称 | 剂型 | 毒性
         | 有效成分及其含量 | 农药类别 | 作物/场所 | 防治对象 | 产品质量标准号

## 这个来源有什么、没有什么

**有**：登记证号、持有人、农药名称、剂型、毒性、有效成分及含量、
农药类别、作物/场所、防治对象 —— 足以完成"该药剂是否登记于本作物 + 本防治对象"的核验。

**没有**：**用药量**与**安全间隔期**。这两项只出现在农药登记标签上，
不在公告 XLS 中。因此本导入器不写这两项，界面与配药换算会如实显示
"剂量请按登记标签"，而不是留一个空字段被误当成"无剂量限制"。

## 归一化约定

- `name`：农药名称原样保留（复配剂形如「丙环·嘧菌酯」）
- `registered_crops`：由「作物/场所」切分，剥掉"田/地/大棚"等场所后缀
- `registered_targets`：防治对象原样保留（如「一年生阔叶杂草」「玉米大斑病」）
- `crop_place` / `category` / `reg_no` / `holder` / `formulation` / `toxicity`
  / `active_ingredients`：原样保留，供追溯与展示
- 与同一农药名称的既有条目**合并**（合并 registered_crops / targets，
  不覆盖已有的 dosage 等字段），幂等可重复导入
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DATA_DIR = Path(__file__).resolve().parent / "data"
# 人工核验的小型权威条目（含剂量/安全间隔期/来源追溯）
PESTICIDE_FILE = DATA_DIR / "pesticide.json"
# 机器导入的批量登记库（公告附件，只含作物/防治对象，无剂量）
REGISTRY_FILE = DATA_DIR / "pesticide_registry.json"

# 知识库覆盖的作物（用于筛选相关登记记录）
TARGET_CROPS = [
    "玉米", "小麦", "马铃薯", "大豆", "棉花", "花生", "高粱", "向日葵", "水稻",
]

# 作物/场所 → 规范作物名。顺序敏感：先长后短，避免「冬小麦」被「小麦」截断前丢失信息。
_CROP_ALIASES = [
    ("冬小麦", "小麦"), ("春小麦", "小麦"), ("小麦", "小麦"),
    ("玉米", "玉米"), ("马铃薯", "马铃薯"), ("土豆", "马铃薯"),
    ("大豆", "大豆"), ("黄豆", "大豆"),
    ("棉花", "棉花"), ("花生", "花生"),
    ("高粱", "高粱"), ("向日葵", "向日葵"), ("油葵", "向日葵"),
    ("水稻", "水稻"),
]

# 需要从"作物/场所"里剥掉的场所后缀（保留在 crop_place 原文中）
_PLACE_SUFFIXES = [
    "移栽田", "直播田", "保护地", "温室", "大棚", "田", "地", "园", "圃",
    "（贮藏期）", "(贮藏期)", "贮藏期",
]

_SPLIT_RE = r"[、,，;；/]+"


def _split(text: str) -> list[str]:
    import re
    return [p.strip() for p in re.split(_SPLIT_RE, str(text or "")) if p.strip()]


def normalize_crop(place: str) -> str:
    """把「冬小麦田」「玉米田」等归一化为规范作物名；识别不到返回空串。"""
    s = str(place or "").strip()
    if not s:
        return ""
    for alias, canon in _CROP_ALIASES:
        if alias in s:
            return canon
    return ""


def normalize_crops(place_field: str) -> list[str]:
    """「作物/场所」→ 规范作物名列表（去重保序）。"""
    out: list[str] = []
    for part in _split(place_field):
        crop = normalize_crop(part)
        if crop and crop not in out:
            out.append(crop)
    return out


def strip_place(place: str) -> str:
    """剥掉场所后缀，便于展示（如「冬小麦田」→「冬小麦」）。"""
    s = str(place or "").strip()
    for suf in _PLACE_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            s = s[: -len(suf)]
            break
    return s.strip()


def is_relevant(record: dict) -> bool:
    """该登记记录是否与知识库覆盖的作物相关。"""
    crops = normalize_crops(record.get("作物/场所", ""))
    if crops:
        return True
    # 部分记录的作物写在防治对象里（如「冬小麦田一年生阔叶杂草」）
    target = str(record.get("防治对象", ""))
    return any(c in target for c in TARGET_CROPS)


def record_to_product(record: dict) -> dict:
    """单条官方登记记录 → 归一化产品条目。"""
    name = str(record.get("农药名称", "")).strip()
    crops = normalize_crops(record.get("作物/场所", ""))
    targets = [t for t in _split(record.get("防治对象", "")) if t]
    reg_no = str(record.get("登记证号", "")).strip()
    return {
        "name": name,
        "registered_crops": crops,
        "registered_targets": targets,
        "crop_place": str(record.get("作物/场所", "")).strip(),
        "category": str(record.get("农药类别", "")).strip(),
        "reg_no": reg_no,
        # 同一通用名可能有多个登记证号，全部记录以便追溯
        "reg_nos": [reg_no] if reg_no else [],
        "holder": str(record.get("登记证持有人", "")).strip(),
        "formulation": str(record.get("剂型", "")).strip(),
        "toxicity": str(record.get("毒性", "")).strip(),
        "active_ingredients": str(record.get("有效成分及其含量", "")).strip(),
    }


def _merge_product(old: dict, new: dict) -> dict:
    """合并同一农药名称的既有条目与新条目（列表字段求并集，其余不覆盖）。"""
    merged = dict(old)
    for key in ("registered_crops", "registered_targets", "reg_nos"):
        vals = list(old.get(key) or [])
        for v in new.get(key) or []:
            if v and v not in vals:
                vals.append(v)
        if vals:
            merged[key] = vals
    # 标量字段：旧值优先（可能是人工核验过的数据），缺失才补
    for key in ("crop_place", "category", "reg_no", "holder", "formulation",
                "toxicity", "active_ingredients"):
        if not merged.get(key) and new.get(key):
            merged[key] = new[key]
    return merged


# 农药类别中文 → pesticide.json 的分组名
_CATEGORY_GROUPS = [
    (("杀菌剂",), "杀菌剂"),
    (("杀虫剂", "杀螨剂"), "杀虫剂"),
    (("除草剂",), "除草剂"),
    (("植物生长调节剂", "杀鼠剂", "卫生杀虫剂"), "其他"),
]


def _group_of(category: str) -> str:
    for keys, group in _CATEGORY_GROUPS:
        if any(k in str(category or "") for k in keys):
            return group
    return "其他"


def load_records(jsonl_path: str | Path) -> list[dict]:
    """读取采集产出的 JSONL。"""
    rows = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_products(records: Iterable[dict]) -> dict[str, dict]:
    """多条登记记录 → {农药名称: 归一化产品}（按名称聚合，列表字段求并集）。"""
    out: dict[str, dict] = {}
    for rec in records:
        if not is_relevant(rec):
            continue
        prod = record_to_product(rec)
        if not prod["name"]:
            continue
        if prod["name"] in out:
            out[prod["name"]] = _merge_product(out[prod["name"]], prod)
        else:
            out[prod["name"]] = prod
    return out


def validate_products(products: dict[str, dict]) -> dict:
    """导入前质量校验：返回问题清单（不静默跳过任何异常）。"""
    from collections import Counter

    problems = {
        "no_crop": [],        # 有防治对象但作物未能归一化
        "no_target": [],      # 有作物但没有防治对象
        "name_too_long": [],  # 名称异常长（可能是解析错位）
        "no_category": [],    # 缺农药类别
    }
    for name, p in products.items():
        if not p.get("registered_crops"):
            problems["no_crop"].append(name)
        if p.get("registered_crops") and not p.get("registered_targets"):
            problems["no_target"].append(name)
        if len(name) > 20:
            problems["name_too_long"].append(name)
        if not p.get("category"):
            problems["no_category"].append(name)
    return {k: {"count": len(v), "sample": v[:8]} for k, v in problems.items()}


def write_registry(products: dict[str, dict],
                   path: Path = REGISTRY_FILE,
                   source_note: str = "") -> dict:
    """把归一化产品写成独立登记库文件（幂等，整体覆盖）。

    为什么单独一个文件、不并进 pesticide.json：
      - `pesticide.json` 是人工逐条核验的小型权威条目（含剂量、安全间隔期、
        登记号、来源链接），必须保持可读、可人工审阅；
      - 公告导入是上千条的机器数据，且只有"作物/防治对象"、没有剂量。
      两者混在一起会让权威条目被淹没，也无法区分"人核验过"与"机器导入"。

    文件结构：
        {
          "_meta": {来源、期数、条数、生成时间},
          "products": [ {...}, ... ]
        }
    """
    import datetime

    payload = {
        "_meta": {
            "source": "农业农村部农药管理司《农药登记信息》公告附件（官方 XLS）",
            "note": source_note,
            "product_count": len(products),
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "fields_note": (
                "本文件仅含登记证号/持有人/农药名称/剂型/毒性/有效成分/类别/"
                "作物场所/防治对象；**不含用药量与安全间隔期**——这两项只出现在"
                "农药登记标签上，请以标签为准。"
            ),
        },
        "products": list(products.values()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return {"written": len(products), "path": str(path)}


def merge_into_pesticide_json(products: dict[str, dict],
                              path: Path = PESTICIDE_FILE,
                              source_note: str = "") -> dict:
    """把归一化产品合并进 pesticide.json（幂等）。

    返回统计：{added, updated, groups, total_after}
    """
    with open(path, "r", encoding="utf-8") as f:
        entries: list[dict] = json.load(f)

    # 建立：分组 → 条目、产品名 → 产品对象（便于原地更新）
    index: dict[str, list[dict]] = {}
    for e in entries:
        index.setdefault(str(e.get("category") or "其他"), []).append(e)

    added = updated = 0
    for name, prod in products.items():
        group = _group_of(prod.get("category", ""))
        bucket = index.get(group) or index.get("其他")
        if not bucket:
            continue
        target_entry = bucket[0]
        prods = target_entry.setdefault("products", [])
        hit = next((p for p in prods if str(p.get("name")) == name), None)
        if hit is None:
            prods.append(prod)
            added += 1
        else:
            merged = _merge_product(hit, prod)
            if merged != hit:
                hit.clear()
                hit.update(merged)
                updated += 1

    if source_note:
        for e in entries:
            e["import_note"] = source_note

    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    total = sum(len(e.get("products") or []) for e in entries)
    return {"added": added, "updated": updated,
            "groups": len(entries), "total_after": total}


__all__ = [
    "TARGET_CROPS", "normalize_crop", "normalize_crops", "strip_place",
    "is_relevant", "record_to_product", "load_records", "build_products",
    "validate_products", "write_registry", "merge_into_pesticide_json",
    "PESTICIDE_FILE", "REGISTRY_FILE",
]
