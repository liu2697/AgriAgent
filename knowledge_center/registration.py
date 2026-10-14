"""
农药登记合规核验（Registration Verifier）。

## 为什么需要它

`pesticide.json` 是**唯一经过登记号核验的权威数据源**（农业农村部农药检定所 ·
中国农药信息网）。而病害条目 `data/*.json` 里的 `registered` / `chemical_control`
是历史资料，存在两类问题：

1. **与权威数据直接冲突**：例如玉米大斑病条目把「苯醚甲环唑」列为登记药剂，
   而 `pesticide.json` 明确记载其登记作物为山药、芝麻、西瓜，**未登记玉米**。
2. **剂量已作废**：病害条目的 `dosage` 写「2000 倍液」，而权威数据说明现行
   登记标签以克/亩、毫升/亩表述，"倍液"未在现行登记标签中核验到。

把这类药剂当"已登记"推荐给农户属于**超范围用药**，是法律风险，
也是本项目最硬的安全底线之一。

## 工作方式（严守"不编造"）

本模块**只做核验与拦截，不生成任何农业事实**：

- 只承认 `pesticide.json` 中有 `registered_crops` / `registered_targets` 的产品；
  缺失即返回 `unverified`（不猜测、不放过、也不断言其违法）。
- 判定为 `unregistered` / `out_of_scope` 时，拒绝在推荐清单中出现。
- 复配剂（名称含「·」）不做单剂推断，返回 `mixture`，交由人工复核。

## 判定级别

| status | 含义 |
|---|---|
| `registered` | 权威数据确认：该作物 + 该防治对象均有登记 |
| `registered_crop_only` | 该作物有登记，但防治对象不同 → 需核对标签 |
| `out_of_scope` | 防效靶标相关，但**未登记该作物** → 超范围用药，不得推荐 |
| `unregistered` | 权威数据确认该产品登记的作物不含本作物 |
| `unverified` | 权威数据未收录该产品 → 无法核验，须核对标签 |
| `mixture` | 复配剂，不做单剂推断 |
| `unknown` | 空名称 |
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# 判定级别
# ---------------------------------------------------------------------------
REGISTERED = "registered"
REGISTERED_CROP_ONLY = "registered_crop_only"
OUT_OF_SCOPE = "out_of_scope"
UNREGISTERED = "unregistered"
UNVERIFIED = "unverified"
MIXTURE = "mixture"
UNKNOWN = "unknown"

# 只有这些级别允许进入"可直接推荐"清单
RECOMMENDABLE = {REGISTERED}

# 级别 → 中文标签（界面与审核摘要使用）
STATUS_LABELS = {
    REGISTERED: "已登记（作物与防治对象均相符）",
    REGISTERED_CROP_ONLY: "该作物已登记，但防治对象不同，须核对标签",
    OUT_OF_SCOPE: "超范围用药风险：未登记该作物",
    UNREGISTERED: "未登记该作物",
    UNVERIFIED: "权威登记数据未收录，无法核验",
    MIXTURE: "复配剂，须核对具体配比登记",
    UNKNOWN: "名称缺失",
}

# 复配剂分隔符（如「丙环·嘧菌酯」「肟菌·戊唑醇」）
_MIXTURE_SEP = "·"


def _tokens(product: dict) -> list[str]:
    """产品在权威数据中声明的登记标识（作物 + 防治对象）。"""
    out: list[str] = []
    for key in ("registered_crops", "registered_targets"):
        for v in product.get(key) or []:
            v = str(v).strip()
            if v:
                out.append(v)
    return out


def _product_has_data(product: dict) -> bool:
    """该产品是否具备可核验的登记声明。"""
    return bool(product.get("registered_crops") or product.get("registered_targets"))


# 登记库缓存：按文件修改时间失效。
# 为什么必须缓存：pesticide_registry.json 约 0.7MB / 1172 条产品，
# `verify_product` 在审计与文本扫描里会被调用成百上千次，
# 每次重解析会让测试从毫秒级变成 75 秒级（实测）。
_REGISTRY_CACHE: dict = {"key": None, "data": None}


def _registry_cache_key():
    from knowledge_center.loader import DATA_DIR
    key = []
    for name in ("pesticide.json", "pesticide_registry.json"):
        p = DATA_DIR / name
        try:
            key.append((name, p.stat().st_mtime_ns, p.stat().st_size))
        except OSError:
            key.append((name, None, None))
    return tuple(key)


def load_registry() -> dict[str, dict]:
    """加载权威登记数据：产品名 → 产品 dict。

    合并两个来源，**人工核验条目优先**（它带剂量、安全间隔期与来源链接）：
      1. `pesticide_registry.json` —— 官方公告附件批量导入（无剂量）
      2. `pesticide.json` —— 人工逐条核验的小型权威条目

    同名产品的登记范围（registered_crops / registered_targets）取并集，
    避免"有剂量但没登记范围"或反之导致无法核验。结果按文件 mtime 缓存。
    """
    from knowledge_center.loader import load_pesticides, load_registry_products

    key = _registry_cache_key()
    if _REGISTRY_CACHE["key"] == key and _REGISTRY_CACHE["data"] is not None:
        return _REGISTRY_CACHE["data"]

    registry: dict[str, dict] = {}
    for prod in load_registry_products() or []:
        name = str(prod.get("name") or "").strip()
        if name:
            registry[name] = dict(prod)

    for entry in load_pesticides() or []:
        for prod in entry.get("products") or []:
            if not isinstance(prod, dict):
                continue
            name = str(prod.get("name") or "").strip()
            if not name:
                continue
            if name not in registry:
                registry[name] = dict(prod)
                continue
            merged = dict(registry[name])
            for k, val in prod.items():
                if k in ("registered_crops", "registered_targets", "reg_nos"):
                    vals = list(merged.get(k) or [])
                    for v in (val or []):
                        if v and v not in vals:
                            vals.append(v)
                    if vals:
                        merged[k] = vals
                elif val:
                    # 人工核验值优先
                    merged[k] = val
            registry[name] = merged

    _REGISTRY_CACHE["key"] = key
    _REGISTRY_CACHE["data"] = registry
    return registry


def known_product_names() -> list[str]:
    """全部有权威数据的产品名（按长度降序，便于从文本中优先匹配长名）。"""
    return sorted(load_registry().keys(), key=len, reverse=True)


def extract_products(text: str) -> list[str]:
    """找出文中提到的、**登记库已收录**的产品名。

    与 `extract_candidate_names` 的区别：只返回登记库里有的名字（即"确定是药"），
    用于消毒/对账等不需要形态猜测的场景。

    实现上复用同一套位置消解：否则「吡唑醚菌酯」会被同时报成
    「吡唑醚菌酯」和它的后缀「醚菌酯」，进而在清洗时把合规药剂拆碎
    （实测出现过）。
    """
    if not text:
        return []
    registry = load_registry()
    return [n for n in extract_candidate_names(text) if n in registry]


# 农药通用名中最具辨识度的收尾字（几乎只出现在农药名中）。
# 必须把「醇」也列上：烯唑醇、戊唑醇、三唑醇都以「醇」收尾，
# 若只列到「唑」，这些名字一个都抓不到（实测漏报过烯唑醇）。
_PESTICIDE_TAIL_CHARS = "唑酯啉酮胺腈肼脲磷威醇"
# 允许出现在收尾字之前 1~2 字的连接字。
# 不能只靠 `[\u4e00-\u9fa5]{2,4}`：那样「唑虫酰胺」会被从「酰」处截断，
# 只得到「酰胺」（长度不足被丢弃），整类"…酰胺"药剂全部漏报（实测）。
_PESTICIDE_LINK_CHARS = "酰氟氯溴碘甲烯啶噻吡苯醚丁戊己辛"
# 出现这些字说明提取到的是中文句子片段而非药剂名（如「止使用吡唑」）。
# 只放高频虚词/介词/助词：这类字几乎不可能出现在农药通用名中。
# 注意不能贪多 —— 曾把「已」「移」也列进来，结果「烯唑醇」被整词误杀。
_NON_NAME_CHARS = set("的了是在和与或请须应不未可需该此及以为用使议荐录验除通过")
# 出现在这些上下文词所在行，才认为是"在推荐用药"
_USE_CONTEXT = (
    "药剂", "用药", "喷雾", "喷施", "撒施", "拌种", "悬浮剂", "可湿性粉剂",
    "水分散粒剂", "水剂", "乳油", "毫升/亩", "克/亩", "倍液",
    "登记", "轮换", "推荐", "安全间隔期",
)


def _is_fragment_of_registered(text: str, name: str, crop: str = "",
                               disease: str = "") -> bool:
    """判断 `name` 是否只是某个更长登记产品名的**片段**（而非独立药剂名）。

    两种片段形态都要处理：
      1. 前缀片段：「苯甲·丙环唑」抓出「丙环唑」，
                   「四唑虫酰胺」抓出「唑虫酰胺」
      2. 后缀片段：「吡唑醚菌酯」抓出「醚菌酯」
         （若不跳过，会把合规药剂拆成「吡唑〔已移除〕」，实测出现过）

    关键区分：`name` **自身也是登记产品**时不算片段。
    否则「吡唑醚菌酯」会因为它是「吡唑醚菌酯·氟啶胺」的子串而被误判为片段
    （每个单剂都是自己复配剂的子串），导致提取结果全空 —— 实测踩过这个坑。
    """
    if not name:
        return False
    registry = load_registry()
    if name in registry:
        return False
    return any(name in other for other in registry if other != name)


def _extract_spans(text: str) -> list[tuple[int, int]]:
    """返回文本中所有"像药剂名"的片段位置（含登记库产品名与形态识别结果）。

    只给位置，不做取舍 —— 由 _resolve_spans 统一处理重叠。
    """
    import re

    spans: set[tuple[int, int]] = set()

    # 1) 登记库里已收录的产品名（全量字符串匹配）
    for name in known_product_names():
        start = 0
        while True:
            i = text.find(name, start)
            if i < 0:
                break
            spans.add((i, i + len(name)))
            start = i + 1

    # 2) 形态识别：在含"用药上下文词"的行内抓 3~5 字药剂名形态
    pat = re.compile(r"[\u4e00-\u9fff]{2,4}[" + _PESTICIDE_TAIL_CHARS + r"]")
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\n\r")
        if len(line) >= 3 and any(ctx in line for ctx in _USE_CONTEXT):
            for m in pat.finditer(line):
                name = m.group(0)
                if not (3 <= len(name) <= 5):
                    continue
                if any(ch in _NON_NAME_CHARS for ch in name):
                    continue
                spans.add((offset + m.start(), offset + m.end()))
        offset += len(raw_line)
    return sorted(spans)


def _resolve_spans(text: str, spans: list[tuple[int, int]]) -> list[str]:
    """从候选位置里挑出真正的药剂名（长优先，被覆盖的丢弃）。

    两条消解规则：
      1. **落在登记库产品名内部**的形态片段直接丢弃。
         例如文本「吡唑醚菌酯」会同时产生 (0,6) 与 (2,6) 两个片段，
         且两者只是部分重叠（并非包含），仅靠规则 2 会两个都留下。
         由于「醚菌酯」本身不在登记库中，它只可能来自这种切分，应丢弃。
      2. 完全被更长候选包含的片段丢弃（长名优先）。

    为什么必须按位置而不是按名字比较：
      「醚菌酯」与「吡唑醚菌酯」是后缀关系，单看名字无法区分
        - 文本 = 「吡唑醚菌酯」 → 醚菌酯是切分残片，丢弃
        - 文本 = 「醚菌酯」      → 被独立引用的真实药剂（登记库收录），保留
      二者名字相同，只有位置能区分。早期用 `name in other` 比较，
      导致要么把合规药剂拆碎、要么整类漏报（两种错都实测踩过）。
    """
    registry = load_registry()

    # 规则 1：丢弃落在某个登记库产品名内部的形态片段
    registry_spans: list[tuple[int, int]] = []
    for name in registry:
        start = 0
        while True:
            i = text.find(name, start)
            if i < 0:
                break
            registry_spans.append((i, i + len(name)))
            start = i + 1

    kept: list[tuple[int, int]] = []
    for s, e in spans:
        frag = text[s:e]
        if frag in registry:
            kept.append((s, e))
            continue
        # 与某个登记库产品名**有任何重叠**就丢弃，不能只判"被包含"。
        # 原因：文本「…如吡唑醚菌酯…」会同时产生登记名 (i, i+6) 与形态片段
        # (i-1, i+4)，二者只是部分重叠而非包含，只判包含会两个都留下，
        # 产生「如吡唑」这种把中文虚词粘进来的假药剂名（实测出现过）。
        if any(max(s, rs) < min(e, re_) for rs, re_ in registry_spans):
            continue
        kept.append((s, e))

    # 规则 2：长优先，完全被包含的丢弃
    picked: list[tuple[int, int]] = []
    for s, e in sorted(kept, key=lambda x: (-(x[1] - x[0]), x[0])):
        if any(ps <= s and e <= pe for ps, pe in picked):
            continue
        picked.append((s, e))
    picked.sort()

    out: list[str] = []
    for s, e in picked:
        name = text[s:e]
        if name and name not in out:
            out.append(name)
    return out


def extract_candidate_names(text: str) -> list[str]:
    """粗提取文中"像农药名"的片段，**包含权威数据未收录的品种**。

    用途：事前白名单只放行已登记药剂，LLM 若仍写出未收录药剂（如「三唑酮」
    「氟吡呋喃酮」），事后闸门必须能发现并拦下。

    实现：先取全部候选位置（登记库产品名 + 形态识别），再按位置消解重叠，
    长片段优先，被覆盖的短片段丢弃。这样「吡唑醚菌酯」不会被拆成
    「吡唑 + 醚菌酯」，而独立出现的「醚菌酯」仍会被保留。

    注意：这是**字符串形态识别**，不是农药事实来源；是否可推荐仍以
    登记库是否收录并登记为准。
    """
    if not text:
        return []
    return _resolve_spans(text, _extract_spans(text))


def verify_product(product_name: str, crop: str, disease: str = "") -> dict:
    """核验单个产品用于「某作物 + 某防治对象」是否在登记范围内。

    返回 dict：status / reason / evidence / product / registered_crops /
    registered_targets。`evidence` 为可追溯的登记依据文本。
    """
    name = str(product_name or "").strip()
    if not name:
        return {"status": UNKNOWN, "product": "", "reason": STATUS_LABELS[UNKNOWN]}

    if _MIXTURE_SEP in name:
        return {
            "status": MIXTURE,
            "product": name,
            "reason": STATUS_LABELS[MIXTURE],
        }

    registry = load_registry()
    prod = registry.get(name)
    if prod is None:
        return {
            "status": UNVERIFIED,
            "product": name,
            "reason": f"权威登记数据（pesticide.json）未收录「{name}」，无法核验",
        }

    crops = [str(c) for c in (prod.get("registered_crops") or [])]
    targets = [str(t) for t in (prod.get("registered_targets") or [])]

    if not _product_has_data(prod):
        # 有该产品条目，但没有可核验的登记声明（如仅 notes 说明未核验到）
        return {
            "status": UNVERIFIED,
            "product": name,
            "reason": f"权威数据中「{name}」未列明登记作物与防治对象，无法核验",
            "registered_crops": crops,
            "registered_targets": targets,
        }

    crop = str(crop or "").strip()
    disease = str(disease or "").strip()

    crop_hit = None
    for c in crops:
        if crop and (c in crop or crop in c):
            crop_hit = c
            break

    # 防治对象是否相符（允许「小麦锈病」↔「小麦条锈病」这类种子级差异）
    target_hit = None
    if disease:
        for t in targets:
            if not t:
                continue
            t_seed = _disease_seed(t)
            d_seed = _disease_seed(disease)
            if t == disease or (t_seed and d_seed and t_seed == d_seed):
                target_hit = t
                break

    evidence = "；".join(
        x for x in (
            f"登记作物：{'、'.join(crops)}" if crops else "",
            f"登记防治对象：{'、'.join(targets)}" if targets else "",
            prod.get("registration_basis") or "",
        ) if x
    )

    if crop_hit and target_hit:
        return {
            "status": REGISTERED, "product": name,
            "reason": STATUS_LABELS[REGISTERED],
            "evidence": evidence, "crop": crop_hit, "target": target_hit,
            "registered_crops": crops, "registered_targets": targets,
        }

    if crop_hit and not target_hit:
        # 泛称覆盖：官方登记的是「叶斑病」这类泛称，而诊断给出「玉米小斑病」。
        # 二者不矛盾（泛称在防效上覆盖细分对象），但也不能直接算"已登记该防治
        # 对象"，因此判为需核对标签（medium，不阻断采纳、提示复核）。
        broad = [t for t in targets if _broad_target_covers(t, disease)]
        if broad:
            return {
                "status": REGISTERED_CROP_ONLY, "product": name,
                "reason": (
                    f"{crop} 已登记；官方登记对象为泛称「{'、'.join(broad)}」，"
                    f"涵盖具体病害「{disease}」，但须核对标签确认防效与用量"
                ),
                "evidence": evidence, "crop": crop_hit, "broad_target": broad[0],
                "registered_crops": crops, "registered_targets": targets,
            }
        return {
            "status": REGISTERED_CROP_ONLY, "product": name,
            "reason": (
                STATUS_LABELS[REGISTERED_CROP_ONLY]
                + (f"（该产品在本作物上登记的是：{'、'.join(targets)}）" if targets else "")
            ),
            "evidence": evidence, "crop": crop_hit,
            "registered_crops": crops, "registered_targets": targets,
        }

    if not crop_hit and not crops and targets:
        # 只声明了防治对象、没声明作物：视为"防效靶标相关但未核验作物"
        return {
            "status": OUT_OF_SCOPE, "product": name,
            "reason": f"仅声明防治对象（{'、'.join(targets)}），未声明登记作物，不能确认可用于{crop}",
            "evidence": evidence,
            "registered_crops": crops, "registered_targets": targets,
        }

    if not crop_hit:
        return {
            "status": UNREGISTERED, "product": name,
            "reason": (
                f"{STATUS_LABELS[UNREGISTERED]}"
                + (f"（现行登记作物为：{'、'.join(crops)}）" if crops else "")
            ),
            "evidence": evidence,
            "registered_crops": crops, "registered_targets": targets,
        }

    return {
        "status": UNVERIFIED, "product": name,
        "reason": STATUS_LABELS[UNVERIFIED],
        "evidence": evidence,
        "registered_crops": crops, "registered_targets": targets,
    }


def _disease_seed(name: str) -> str:
    """取病害名的"特征词"，用于容忍「小麦锈病 / 小麦条锈病」这类差异。"""
    s = str(name or "").strip()
    if not s:
        return ""
    s = s.replace("病", "")
    for prefix in ("冬小麦田", "一年生", "阔叶", "杂草", "田"):
        s = s.replace(prefix, "")
    for crop in ("玉米", "小麦", "马铃薯", "大豆", "棉花", "花生", "高粱",
                 "向日葵", "水稻", "山药", "芝麻", "西瓜", "冬小麦"):
        s = s.replace(crop, "")
    return s.strip()


# 官方登记里常见"泛称"防治对象，以及它们覆盖的细分对象。
# 例：多菌灵登记对象是「叶斑病」（泛称），而病害条目写的是「玉米小斑病」；
# 二者并非矛盾，属"泛称覆盖细分"，应判为"需核对标签"而非"超范围用药"。
# 只收录确无歧义的泛称，避免把真正的超范围用药放过去。
_BROAD_TARGETS: dict[str, tuple[str, ...]] = {
    "叶斑病": ("斑病", "叶斑", "褐斑", "黑斑", "圆斑", "轮纹", "早疫", "晚疫"),
    "叶枯病": ("叶枯", "枯斑"),
    "锈病": ("锈病", "条锈", "叶锈", "秆锈"),
    "白粉病": ("白粉",),
    "纹枯病": ("纹枯",),
    "赤霉病": ("赤霉",),
    "菌核病": ("菌核",),
    "疫病": ("疫病", "晚疫", "早疫"),
    "霜霉病": ("霜霉",),
    "炭疽病": ("炭疽",),
    "灰霉病": ("灰霉",),
    "黑星病": ("黑星",),
    "炭疽病 ": ("炭疽",),
    "蚜虫": ("蚜",),
    "螟虫": ("螟",),
    "蓟马": ("蓟马",),
    "飞虱": ("飞虱",),
    "红蜘蛛": ("红蜘蛛", "叶螨"),
}


def _broad_target_covers(target: str, disease: str) -> bool:
    """官方泛称防治对象是否覆盖该具体病害名。"""
    t = str(target or "").strip()
    d = str(disease or "").strip()
    if not t or not d:
        return False
    subs = _BROAD_TARGETS.get(t)
    if not subs:
        # 退化规则：泛称去掉"病"字后，是否为病害名的组成部分
        core = t.replace("病", "").replace("虫", "")
        return bool(core) and len(core) >= 2 and core in d
    return any(sub in d for sub in subs)


def audit_disease_entry(entry: dict) -> dict:
    """审计单条病害条目的用药清单，标出超范围/无法核验项。

    只读，不修改入参，也不写回数据文件。
    """
    crop = str(entry.get("crop") or "")
    disease = str(entry.get("disease") or "")
    listed: list[str] = []
    for key in ("chemical_control",):
        listed.extend(str(v).strip() for v in (entry.get(key) or []) if str(v).strip())
    ref = entry.get("pesticide_reference") or {}
    listed.extend(str(v).strip() for v in (ref.get("registered") or []) if str(v).strip())

    seen: set[str] = set()
    results = []
    for name in listed:
        if name in seen:
            continue
        seen.add(name)
        results.append(verify_product(name, crop, disease))

    return {
        "crop": crop,
        "disease": disease,
        "products": results,
        "registered": [r["product"] for r in results if r["status"] == REGISTERED],
        "blocked": [
            r["product"] for r in results
            if r["status"] in (OUT_OF_SCOPE, UNREGISTERED)
        ],
        "needs_review": [
            r["product"] for r in results
            if r["status"] in (REGISTERED_CROP_ONLY, UNVERIFIED, MIXTURE)
        ],
        "legacy_dosage": str(ref.get("dosage") or ""),
    }


def audit_all() -> list[dict]:
    """全库审计（维护用）：找出所有条目里超范围/无法核验的用药项。"""
    from knowledge_center.loader import load_diseases

    return [audit_disease_entry(e) for e in (load_diseases() or [])]


def registered_products_for(crop: str, disease: str = "") -> list[dict]:
    """返回可用于「某作物 + 某防治对象」的权威登记产品（可直接推荐）。"""
    out = []
    for name, prod in load_registry().items():
        r = verify_product(name, crop, disease)
        if r["status"] in RECOMMENDABLE:
            out.append({
                "name": name,
                "dosage": prod.get("typical_dosage") or "",
                "safety_interval_days": prod.get("safety_interval_days"),
                "max_uses_per_season": prod.get("max_uses_per_season"),
                "registration_basis": prod.get("registration_basis") or "",
                "notes": prod.get("notes") or "",
            })
    return out


def filter_recommendable(names: list[str], crop: str, disease: str = "") -> tuple[list[str], list[dict]]:
    """把候选药剂分成 (可直接推荐, 被拦截项)。

    被拦截项包含原因，供审核摘要与界面提示展示。
    """
    keep: list[str] = []
    blocked: list[dict] = []
    seen: set[str] = set()
    for name in names or []:
        nm = str(name).strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        r = verify_product(nm, crop, disease)
        if r["status"] in RECOMMENDABLE:
            keep.append(nm)
        else:
            blocked.append(r)
    return keep, blocked


# 剔除后的占位文本。用纯符号，避免任何中文片段被形态识别误当成药剂名。
REDACTION_MARK = "〔已移除〕"


def sanitize_pesticide_mentions(text: str, crop: str, disease: str = "",
                                names: list[str] | None = None) -> tuple[str, list[dict]]:
    """把未通过登记核验的药剂名从用药建议中剔除。

    为什么必须"剔除"而不只是"提示"：实测即使 Prompt 明确禁止，通用大模型
    仍会写出未登记本作物的药剂（如玉米大斑病建议里出现苯醚甲环唑）。
    只标记不清理的话，农户照样会照着用 —— 等于把合规风险原样交到农户手上。

    参数 `names`：
      - 传入时，只清理这些确切的药剂名（用于"已知候选集合"的清洗，如知识库
        参考区块）。这类场景必须精确，不能做形态猜测。
      - 不传时（None），用形态识别+登记库匹配尽量全地找出药剂名（用于清洗
        LLM 自由生成的正文）。

    形态识别的已知风险：会把长名的片段当独立药剂名（如「醚菌酯」是
    「吡唑醚菌酯」的片段），从而把合规药剂误拆成 `吡唑〔已移除〕`。
    因此凡是被某个**登记范围内**产品名包含的候选，一律跳过不清理。

    返回 (清理后文本, 被剔除项列表)。仅做字符串替换，不新增任何农业事实。
    """
    if not text:
        return text, []

    removed: list[dict] = []
    result = text

    if names is not None:
        candidates = [str(n).strip() for n in names if str(n).strip()]
    else:
        candidates = extract_candidate_names(text)
        for n in extract_products(text):
            if n not in candidates:
                candidates.append(n)

    # 长名优先替换，避免「苯甲·丙环唑」中的片段先被替换破坏整体
    for name in sorted(set(candidates), key=len, reverse=True):
        verdict = verify_product(name, crop, disease)
        if verdict["status"] in RECOMMENDABLE:
            continue
        if name in result:
            result = result.replace(name, REDACTION_MARK)
            if not any(r["product"] == name for r in removed):
                removed.append(verdict)

    return result, removed


def registration_disclaimer(removed: list[dict]) -> str:
    """为被剔除的药剂生成一段透明的说明（可选附加到报告中）。"""
    if not removed:
        return ""
    names = "、".join(str(r.get("product") or "") for r in removed if r.get("product"))
    if not names:
        return ""
    return (
        f"> 说明：本报告中「{names}」未通过现行农药登记核验"
        "（未登记于本作物或权威数据未收录），已由系统移除，"
        "不得作为用药依据。请按已核验药剂或农药标签选用。"
    )


__all__ = [
    "REGISTERED", "REGISTERED_CROP_ONLY", "OUT_OF_SCOPE", "UNREGISTERED",
    "UNVERIFIED", "MIXTURE", "UNKNOWN", "RECOMMENDABLE", "STATUS_LABELS",
    "REDACTION_MARK",
    "load_registry", "known_product_names", "extract_products",
    "extract_candidate_names", "verify_product", "audit_disease_entry",
    "audit_all", "registered_products_for", "filter_recommendable",
    "sanitize_pesticide_mentions",
]
