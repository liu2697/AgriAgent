"""
作物名称统一解析（别名 / 地方俗称 → 规范作物名）。

## 为什么需要它

农户不会按规范名输入作物。北方大田常见的写法包括：

    玉米     → 苞米、棒子、苞谷、玉蜀黍、corn
    马铃薯   → 土豆、洋芋、山药蛋、potato
    谷子     → 小米、粟、黄粟
    糜子     → 黍子、稷、黄米
    油菜     → 油菜籽、芸薹、菜籽
    甜菜     → 糖甜菜、糖萝卜

如果只按规范名匹配，农户写"土豆"，系统会当成未知作物、
检索不到任何知识条目，最终只能靠通用大模型自由发挥 —— 这正是要避免的。

## 设计原则

- 本模块**只做名称映射**，不生成任何农业事实。
- 别名表覆盖常见俗称与英文名；解析采用"规范化 + 别名精确 + 子串包含"三级，
  例如「冬小麦田」能解析到「小麦」。
- 无法识别时返回空字符串（`resolve_crop`），或返回 None（`resolve_crop_or_none`），
  由调用方决定是提示农户补充、还是按通用模式处理。
"""
from __future__ import annotations

import re

# 规范作物名 → 别名 / 地方俗称 / 英文名
CROP_ALIASES: dict[str, list[str]] = {
    # ---- 原有 8 种 ----
    "玉米": ["苞米", "苞谷", "棒子", "玉蜀黍", "玉米棒", "corn", "maize"],
    "小麦": ["麦子", "冬小麦", "春小麦", "麦", "wheat"],
    "马铃薯": ["土豆", "洋芋", "山药蛋", "洋山芋", "荷兰薯", "potato"],
    "大豆": ["黄豆", "青豆", "毛豆", "黑豆", "soybean", "soy"],
    "棉花": ["棉", "陆地棉", "cotton"],
    "花生": ["落花生", "长生果", "地豆", "peanut", "groundnut"],
    "高粱": ["蜀黍", "红粮", "秫秫", "sorghum"],
    "向日葵": ["油葵", "葵花", "朝阳花", "sunflower"],
    # ---- 新增：北方主要大田作物 ----
    "水稻": ["稻", "稻子", "早稻", "中稻", "晚稻", "粳稻", "籼稻", "rice", "paddy"],
    "谷子": ["粟", "小米", "黄粟", "谷", "foxtail millet", "millet"],
    "糜子": ["黍子", "稷", "黄米", "糜", "broomcorn millet", "proso millet"],
    "燕麦": ["莜麦", "燕麦草", "皮燕麦", "oats", "oat"],
    "荞麦": ["甜荞", "苦荞", "三角麦", "花荞", "buckwheat"],
    "大麦": ["啤麦", "元麦", "稞麦", "裸大麦", "barley"],
    "甜菜": ["糖甜菜", "糖萝卜", "饲用甜菜", "sugar beet", "beet"],
    "油菜": ["油菜籽", "芸薹", "菜籽", "冬油菜", "rapeseed", "canola"],
    "芝麻": ["脂麻", "油麻", "sesame"],
    "亚麻": ["胡麻", "油用亚麻", "纤用亚麻", "flax", "linseed"],
    "绿豆": ["青小豆", "植豆", "mung bean"],
    "豌豆": ["寒豆", "麦豌豆", "peas", "pea"],
    "蚕豆": ["胡豆", "罗汉豆", "佛豆", "faba bean"],
    "红小豆": ["赤小豆", "小豆", "红豆", "adzuki bean"],
    "苜蓿": ["紫花苜蓿", "牧草苜蓿", "alfalfa"],
    "蓖麻": ["大麻子", "红蓖麻", "castor"],
}

# 需要剥离的场所/用途后缀，便于「冬小麦田」「玉米地块」这类写法解析
_PLACE_SUFFIXES = [
    "移栽田", "直播田", "保护地", "温室", "大棚", "地块", "田", "地", "园", "圃",
    "（贮藏期）", "(贮藏期)", "贮藏期",
]

_NORM_RE = re.compile(r"[\s　,，。.、;；:：/\\()（）\[\]【】\"'`]+")


def _normalize(text: str) -> str:
    return _NORM_RE.sub("", str(text or "").strip().lower())


def _strip_place(text: str) -> str:
    s = str(text or "").strip()
    for suf in _PLACE_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)].strip()
    return s


def _alias_index() -> list[tuple[str, str]]:
    """(别名, 规范名) 列表，按别名长度降序，保证长名优先匹配。"""
    pairs: list[tuple[str, str]] = []
    for canon, aliases in CROP_ALIASES.items():
        pairs.append((canon, canon))
        for a in aliases:
            if a:
                pairs.append((a, canon))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def resolve_crop(raw: str) -> str:
    """把农户输入的作物名解析为规范作物名；无法识别返回空字符串。

    匹配顺序：
      1. 规范化后精确匹配规范名或别名（含剥离场所后缀再试）
      2. 子串包含匹配（如「内蒙古马铃薯」→ 马铃薯）
    """
    text = _normalize(raw)
    if not text:
        return ""

    candidates = {text}
    stripped = _normalize(_strip_place(raw))
    if stripped:
        candidates.add(stripped)

    for alias, canon in _alias_index():
        key = _normalize(alias)
        if key and key in candidates:
            return canon

    # 子串包含：别名出现在输入中（别名长度≥2，避免「麦」误伤）
    for alias, canon in _alias_index():
        key = _normalize(alias)
        if len(key) >= 2 and key in text:
            return canon
    return ""


def resolve_crop_or_none(raw: str) -> str | None:
    """同 resolve_crop，但无法识别时返回 None（便于区分"空输入"与"未识别"）。"""
    got = resolve_crop(raw)
    return got or None


def known_crops() -> list[str]:
    """全部规范作物名（按别名表顺序）。"""
    return list(CROP_ALIASES.keys())


def aliases_of(crop: str) -> list[str]:
    return list(CROP_ALIASES.get(str(crop or "").strip(), []))


__all__ = [
    "CROP_ALIASES", "resolve_crop", "resolve_crop_or_none",
    "known_crops", "aliases_of",
]
