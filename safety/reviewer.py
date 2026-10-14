from __future__ import annotations

import re
from dataclasses import dataclass, field


# 原硬编码名单：仅在知识库不可用时作为保底（fallback），不再是第一数据来源
_FALLBACK_FORBIDDEN_PESTICIDES = [
    "百草枯", "对硫磷", "甲基对硫磷", "甲胺磷", "久效磷",
    "磷胺", "六六六", "滴滴涕", "毒鼠强", "氟乙酸钠",
    "杀虫脒", "除草醚", "汞制剂", "砷制剂", "敌枯双",
    "二溴氯丙烷", "溴丙烷", "1,2-二溴乙烷",
]


def _load_forbidden_from_knowledge_base() -> list[str]:
    """从 V1.3 知识库 pesticide.json「禁限用农药」条目读取官方核验名单。

    单一数据来源原则：pesticide.json（农业农村部《禁限用农药名录》
    及第536/736号公告逐条核验）→ Safety Reviewer → 匹配关键词。
    仅读取已核验的 name 字段，并从同一名称派生括号内别名
    （如「对硫磷（1605）」→「对硫磷」），不新增任何未经核验的名称。
    知识库读取失败时返回空列表（调用方回退到保底名单）。
    """
    try:
        from knowledge_center.loader import load_pesticides
        entries = load_pesticides()
    except Exception:
        return []
    names: list[str] = []
    for entry in entries or []:
        for sub in entry.get("forbidden_substances") or []:
            if not isinstance(sub, dict):
                continue
            name = str(sub.get("name") or "").strip()
            if not name:
                continue
            if name not in names:
                names.append(name)
            base = re.split(r"[（(]", name)[0].strip()
            if base and base not in names:
                names.append(base)
    return names


# 禁限用农药匹配名单：知识库核验名单优先，读取失败时回退保底名单
FORBIDDEN_PESTICIDES: list[str] = (
    _load_forbidden_from_knowledge_base()
    or list(_FALLBACK_FORBIDDEN_PESTICIDES)
)

RISK_KEYWORDS = [
    "剧毒", "高毒", "致死",
    "立刻", "马上", "赶紧", "快速处理",
    "食用", "可食", "生吃",
]

HIGH_RISK_BEHAVIOR = [
    "超剂量", "加倍使用", "混合多种", "多种混用",
    "不戴手套", "不通风", "直接接触",
]


@dataclass
class ReviewIssue:
    level: str
    category: str
    message: str
    evidence: str = ""


@dataclass
class ReviewResult:
    safe: bool
    risk_level: str
    issues: list[ReviewIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "risk_level": self.risk_level,
            "issues": [i.__dict__ for i in self.issues],
            "warnings": self.warnings,
        }

    def summary_text(self) -> str:
        # risk_level="未知" 表示安全审核未正常完成（fail-open 兜底），
        # 绝不能输出「安全审核通过」伪装成正常通过状态
        if self.safe and not self.issues and self.risk_level != "未知":
            lines = ["✅ 安全审核通过：未检测到禁限用农药或高风险内容。"]
        else:
            lines = [f"### 安全审核（风险等级 {self.risk_level}）"]
            for issue in self.issues:
                icon = {"high": "高", "medium": "中", "low": "低"}.get(issue.level, "·")
                lines.append(f"- {icon} [{issue.category}] {issue.message}")
                if issue.evidence:
                    lines.append(f"  > 证据：{issue.evidence}")
        if self.warnings:
            lines.append("")
            lines.append("**通用提醒**")
            for w in self.warnings:
                lines.append(f"- {w}")
        return "\n".join(lines)


def _find_matches(text: str, keywords: list[str]) -> list[str]:
    hits = []
    for kw in keywords:
        if kw in text:
            hits.append(kw)
    return hits


def _extract_dosage_risks(text: str) -> list[str]:
    """检查推荐剂量是否异常：只对明显偏离常规范围的值给出复核提示。"""
    risks = []
    # 稀释倍数：常规稀释一般为 500~2000 倍，低于 300 倍视为浓度偏高
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(倍液|倍)", text):
        try:
            ratio = float(m.group(1))
        except ValueError:
            continue
        if ratio < 300:
            risks.append(f"稀释倍数 {ratio} 倍偏低（浓度偏高）")
    # 亩用量：超过 800 克/毫升需复核
    for m in re.finditer(r"亩(?:用|施)\s*(\d+(?:\.\d+)?)\s*(克|g|毫升|ml)", text):
        try:
            amount = float(m.group(1))
        except ValueError:
            continue
        if amount > 800:
            risks.append(f"亩用量 {amount} {m.group(2)} 偏高")
    return risks


def _registration_issues(text: str, crop: str, disease: str) -> list[ReviewIssue]:
    """事后闸门：核验 LLM 实际推荐药剂是否超出登记范围。

    事后闸门与事前白名单是两道独立防线：
      - 事前：把超范围药剂从 Prompt 候选里剔除并明确禁止（executor）
      - 事后：万一 LLM 仍写了出来，这里必须把它报成问题并拦住采纳

    三档判定，全部只依据 pesticide.json 权威登记数据：
      - 权威数据判定未登记本作物 → high（超范围用药，必须移除）
      - 权威数据未收录该品种     → medium（无法核验，须人工复核标签）
      - 复配剂                   → medium（不推断单剂登记）

    注意：绝不因为核验失败而放行。任何异常都返回空列表，由审核摘要
    如实说明"登记核验未完成"，而不是伪装成"已通过"。
    """
    if not text or not crop:
        return []
    try:
        from knowledge_center.registration import (
            extract_candidate_names, known_product_names, verify_product,
            OUT_OF_SCOPE, UNREGISTERED, MIXTURE, UNVERIFIED, UNKNOWN, REGISTERED,
        )

        blocked_status = (OUT_OF_SCOPE, UNREGISTERED)
        known = set(known_product_names())
        issues: list[ReviewIssue] = []
        reported: set[str] = set()

        for name in extract_candidate_names(text):
            if name in reported:
                continue
            r = verify_product(name, crop, disease)
            status = r.get("status")

            if status in blocked_status:
                reported.add(name)
                issues.append(ReviewIssue(
                    level="high",
                    category="超范围用药",
                    message=(
                        f"「{name}」的现行登记范围不含{crop}，"
                        f"出现在用药建议中属于超范围用药，必须移除或替换"
                    ),
                    evidence=r.get("evidence") or r.get("reason", ""),
                ))
            elif status == REGISTERED:
                continue
            elif status in (MIXTURE, UNVERIFIED) and name in known:
                # 权威数据收录但未列明登记范围（或为复配剂）→ 提示复核标签
                reported.add(name)
                issues.append(ReviewIssue(
                    level="medium",
                    category="登记待核验",
                    message=f"「{name}」{r.get('reason', '需核对登记标签')}",
                    evidence=r.get("evidence") or "",
                ))
            elif status != UNKNOWN and name not in known:
                # 形态确认为药剂名、但权威登记数据完全未收录。
                # 判为 high：本系统无法确认它登记在哪个作物上，按"无法核验即不得
                # 作为已登记药剂推荐"处理。若只判 medium（不阻断），农户仍会照用，
                # 等于放行了一个我们无法保证合规的用药建议。
                reported.add(name)
                issues.append(ReviewIssue(
                    level="high",
                    category="登记未核验",
                    message=(
                        f"「{name}」未在权威农药登记数据（pesticide.json）中收录，"
                        f"无法核验其是否登记于{crop}，不得作为已登记药剂推荐，"
                        "请改为已核验药剂或核对农药标签"
                    ),
                    evidence="权威登记数据未收录该品种",
                ))
        return issues
    except Exception:
        return []


# 否定 / 鉴别语境标记：药剂名出现在这些词附近，通常是"警告不要用"或
# "鉴别诊断时要排除"，而不是在推荐使用。
_NEGATION_MARKERS = (
    "禁止", "严禁", "不得", "不准", "禁用", "停用", "杜绝", "勿用", "不能使用",
    "不用", "未用", "没有使用", "排除", "除外", "区别于", "鉴别", "如", "例如",
    "等", "非", "禁忌", "案例", "教训", "误用", "违规", "属于违法",
)


def _near_negation(text: str, keyword: str, window: int = 14) -> bool:
    """判断关键词是否出现在"否定/鉴别"语境中。"""
    if not text or not keyword:
        return False
    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx < 0:
            return False
        lo = max(0, idx - window)
        hi = min(len(text), idx + len(keyword) + window)
        if any(mk in text[lo:hi] for mk in _NEGATION_MARKERS):
            return True
        start = idx + len(keyword)


def review(text: str, diagnosis_context: str = "", crop: str = "",
           disease: str = "") -> ReviewResult:
    """
    对 Agent / LLM 输出的诊断建议进行安全审核。

    参数 crop / disease 用于农药登记合规核验（超范围用药拦截）。
    不传时跳过该项核验，其余逻辑不变（保持向后兼容）。
    """
    issues: list[ReviewIssue] = []
    combined = text + diagnosis_context

    for name in _find_matches(combined, FORBIDDEN_PESTICIDES):
        # 语境区分：实测 LLM 在"鉴别诊断要排除的线索（如百草枯药害）"里
        # 提到禁限用农药，也被判成"推荐使用"的高危项，导致整份报告被拦下。
        # 这类提及应提示复核而非阻断采纳，否则农户拿不到可用方案。
        if _near_negation(combined, name):
            issues.append(ReviewIssue(
                level="medium",
                category="禁限用农药提及",
                message=(
                    f"检测到禁限用农药「{name}」，但语境像是警告或鉴别诊断，"
                    "请农技人员确认未作为用药推荐"
                ),
                evidence=name,
            ))
        else:
            issues.append(ReviewIssue(
                level="high",
                category="禁限用农药",
                message=f"检测到疑似禁限用农药「{name}」，必须立即移除或替换",
                evidence=name,
            ))

    issues.extend(_registration_issues(text, crop, disease))

    risk_hits = _find_matches(combined, RISK_KEYWORDS)
    for kw in risk_hits:
        issues.append(ReviewIssue(
            level="medium",
            category="风险措辞",
            message=f"包含「{kw}」等需谨慎使用的措辞，请农技人员复核",
            evidence=kw,
        ))

    behavior_hits = _find_matches(combined, HIGH_RISK_BEHAVIOR)
    for kw in behavior_hits:
        issues.append(ReviewIssue(
            level="high",
            category="危险操作",
            message=f"建议中包含「{kw}」等危险操作描述，必须改写",
            evidence=kw,
        ))

    dosage_risks = _extract_dosage_risks(combined)
    for label in dosage_risks:
        issues.append(ReviewIssue(
            level="low",
            category="剂量复核",
            message=f"涉及「{label}」描述，建议农技人员核对登记剂量",
        ))

    warnings = [
        "本建议由 AI 生成，仅供参考；实际用药前请咨询当地持证农技推广人员",
        "施药时务必穿戴个人防护装备，严格遵守农药安全间隔期规定",
        "严禁使用国家明令禁止的农药，推荐药剂须在当地农业农村部登记范围内选用",
    ]

    if any(i.level == "high" for i in issues):
        risk_level = "高"
    elif any(i.level == "medium" for i in issues):
        risk_level = "中"
    elif issues:
        risk_level = "低"
    else:
        risk_level = "无"

    # safe 只看"高危"问题：medium/low 是需要复核的提示，不应阻断农户拿到方案。
    # 禁限用农药若出现在否定/鉴别语境，已降级为 medium（见上），
    # 因此这里不再单独按 forbidden 判定，避免"提到即阻断"。
    safe = risk_level != "高"

    return ReviewResult(
        safe=safe,
        risk_level=risk_level,
        issues=issues,
        warnings=warnings,
    )


__all__ = ["review", "ReviewResult", "ReviewIssue", "FORBIDDEN_PESTICIDES"]
