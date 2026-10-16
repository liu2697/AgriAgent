# -*- coding: utf-8 -*-
"""诊断内容的"农户友好"精简摘要（农户端与农技员端共用一套逻辑，保证两端一致）。

设计目标（按用户要求）：
  · 生成内容长度稳定在 **80–100 字**（特殊情况可放宽，如安全审核未通过需展示原文证据）；
  · 只讲"下一步该怎么做"和"可以着手准备的方案"，去掉推理过程、可能性排序、免责话术等；
  · 关键动作/药剂/剂量加粗，便于农户一眼抓到重点；
  · 农技员端复用同一摘要，并可就地展开完整原文。

对外只暴露两个函数：
  brief_next_steps(content, ...) -> list[str]   取 2–3 条要点（总字数尽量落在 80–100）
  render_brief_html(items, title=...) -> str    渲染为带加粗的 HTML 要点块
"""
from __future__ import annotations

import html
import re

MAX_TOTAL = 100          # 目标总字数上限
MIN_TOTAL = 80           # 目标总字数下限（内容太短时不强求）
MAX_ITEMS = 3            # 最多条数

# 动作词：句子里有这些词，才说明"农户能照着做"
_ACTION_WORDS = (
    "喷", "施药", "用药", "防治", "清除", "清理", "摘除", "剪除", "拔除", "轮换", "轮作",
    "控制", "增施", "追肥", "施肥", "灌溉", "浇水", "排水", "排涝", "巡查", "巡田",
    "监测", "复查", "咨询", "间隔", "稀释", "兑水", "翻耕", "选种", "包衣", "播种",
    "晚播", "停用", "避免", "注意", "及时", "加强", "保持", "使用", "处理", "上报",
)

# 剂量/频次类数字（只有这类数字才算"可执行"，"1–3 mm"这类形态描述不算）
_DOSE_RE = re.compile(
    r"\d+(?:\.\d+)?(?:\s*[-–~至到]\s*\d+(?:\.\d+)?)?\s*"
    r"(?:克|千克|公斤|毫升|升|亩|天|次|倍|%|g|ml|L)"
)

# 需要剔除的"非行动"句子（推理、依据、免责、元信息）
_NOISE_MARKERS = (
    "可能性", "依据：", "依据:", "相关性", "本结论", "仅供参考", "辅助判断", "未提及",
    "只有", "建议咨询", "知识库", "已为你排除", "说明：", "备注", "评分", "确诊",
    "理由", "因此", "结论：", "判断依据", "符合", "不符合", "不支持", "概率",
    "典型症状", "症状", "观察", "直径", "形态", "颜色",
)

# 章节优先级：先讲"怎么治"，再讲"怎么管"，最后提示风险
_SECTION_PRIORITY = ("防治", "用药", "处理", "农事", "管理", "建议", "风险", "注意")


def _clean_markdown(text: str) -> str:
    """去掉 Markdown 记号，保留纯文本行。"""
    t = text or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"^\s*[-*+•·]\s+", "", t, flags=re.M)
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)
    return t


def _iter_lines(content: str):
    """按行产出"清洗后、去掉行首编号/符号"的句子（跳过小标题与纯标签行）。"""
    for raw in _clean_markdown(content).splitlines():
        ln = raw.strip()
        # 去掉句首符号/表情及其不可见组合字符（⚠️ 的 U+FE0F、零宽字符等）
        ln = re.sub(r"^[\s\ufe0f\u200b\u200d\ufeff⚠✅❌🔴⛔◆●■※]+", "", ln)
        ln = re.sub(r"^[（(]?\d{1,2}[）)、.．:：]\s*", "", ln)  # 去掉行首编号
        ln = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*", "", ln).strip()
        ln = ln.rstrip("：: ").strip()                        # 去掉结尾悬空冒号
        if len(ln) < 8:
            continue
        if ln.endswith(("：", ":")) and len(ln) <= 32:
            continue
        if any(m in ln for m in _NOISE_MARKERS):
            continue
        yield ln


def _is_actionable(ln: str) -> bool:
    """可执行 = 含动作词，或含剂量/频次类数字。"""
    return any(w in ln for w in _ACTION_WORDS) or bool(_DOSE_RE.search(ln))


def _section_of(line: str, current: str) -> str:
    return current


def _split_by_section(content: str) -> dict[str, list[str]]:
    """按标题把正文分成若干段，键为标题文字（用于按优先级取用）。"""
    sections: dict[str, list[str]] = {}
    title = ""
    for raw in (content or "").splitlines():
        head = re.match(r"^\s{0,3}#{1,6}\s*(.+?)\s*$", raw) or \
               re.match(r"^\s*(\d{1,2}[.、]\s*[^：:\n]{2,20})\s*$", raw)
        if head:
            title = head.group(1)
            sections.setdefault(title, [])
            continue
        sections.setdefault(title, []).append(raw)
    return sections


def _pick_action_lines(content: str) -> list[str]:
    """按章节优先级挑出"动作句"：先防治/用药，再农事/管理，最后风险提示。"""
    sections = _split_by_section(content)
    ordered: list[str] = []

    def collect(title_filter=None):
        for title, body in sections.items():
            if title_filter and not any(k in title for k in title_filter):
                continue
            for ln in _iter_lines("\n".join(body)):
                if _is_actionable(ln):
                    ordered.append(re.sub(r"（[^）]{20,}）", "", ln).strip() or ln)

    collect(_SECTION_PRIORITY)                 # 1) 优先：防治/用药/农事/管理/风险
    if len(ordered) < 3:                       # 2) 不足时再从全文兜底
        collect(None)
    # 去重（保序）
    seen, out = set(), []
    for ln in ordered:
        key = ln[:14]
        if key not in seen:
            seen.add(key)
            out.append(ln)
    return out


def _trim(sentence: str, limit: int) -> str:
    """把句子裁到 limit 字以内（优先在标点处断开）。"""
    if len(sentence) <= limit:
        return sentence
    window = sentence[: limit + 6]
    cut = max(window.rfind(p) for p in "。；;，,、")
    if cut >= 10:
        return sentence[:cut].rstrip("，,、；;") + "…"
    return sentence[:limit].rstrip("，,、；;（(0123456789 ") + "…"


def brief_next_steps(content: str, *, max_total: int = MAX_TOTAL,
                     max_items: int = MAX_ITEMS) -> list[str]:
    """取 2–3 条"下一步怎么做"的要点，总字数尽量落在 80–100 字。

    · 优先保证条数（2–3 条）与可执行性；
    · 累加过程中一旦达到 max_total 就停止；单条最多给到 46 字；
    · 特殊情况（内容确实很短，如示例模式/极简报告）允许不足 80 字。
    """
    candidates = _pick_action_lines(content)
    if not candidates:
        return []

    picked: list[str] = []
    total = 0
    # 目标：每条大致均分预算，先按条数分配上限，再逐条累加
    per_item = max(26, min(46, max_total // max(1, min(len(candidates), max_items))))
    for ln in candidates:
        if len(picked) >= max_items:
            break
        item = _trim(ln, per_item).rstrip("：: ").strip()
        # 若加上这条会明显超出预算，且已有 2 条以上 → 停止
        if picked and total + len(item) > max_total + 8:
            break
        picked.append(item)
        total += len(item)
    return picked


def emphasize_line(text: str) -> str:
    """加粗重点：标签、药剂名（短名+括号）、剂量/间隔期等数字。"""
    t = html.escape(text)
    colon = min([i for i in (t.find("："), t.find(":")) if i != -1], default=-1)
    if 0 < colon <= 16 and not re.search(r"[，,。；;、]", t[:colon]):
        t = f"<strong>{t[:colon]}</strong>" + t[colon:]
    else:
        m = re.match(r"^([^：:（(，,。；;、\s]{2,6})[（(]", t)
        if m:
            t = f"<strong>{m.group(1)}</strong>" + t[m.end(1):]
    t = re.sub(
        r"(\d+(?:\.\d+)?(?:\s*[-–~至到]\s*\d+(?:\.\d+)?)?\s*"
        r"(?:克|千克|公斤|毫升|升|亩|天|次|倍|%|g|ml|L))",
        r"<strong>\1</strong>", t,
    )
    return t


def render_brief_html(items: list[str], *, title: str = "接下来这样做",
                      cls: str = "ag-rpt-current") -> str:
    """渲染精简摘要块（无内容时返回空串，由调用方决定兜底）。"""
    if not items:
        return ""
    lis = "".join(f"<li>{emphasize_line(x)}</li>" for x in items)
    cls_attr = f"ag-rpt-advice-block {cls}".strip()
    return (
        f'<div class="{cls_attr}">'
        f'<div class="ag-rpt-advice-title"><span class="bullet"></span>{title}</div>'
        f'<ul class="ag-rpt-brief">{lis}</ul>'
        f'</div>'
    )


def brief_total_chars(items: list[str]) -> int:
    return sum(len(x) for x in items)


# =============================================================================
# 管理端（农技员）专用：不加任何表情，重点加粗、风险点标红、章节自动编号
# =============================================================================

# 风险类关键词：命中即标红加粗，便于农技员一眼看到要害
_DANGER_WORDS = (
    "禁用", "严禁", "超标", "超范围", "未登记", "未核验", "高风险", "不得",
    "违规", "违法", "立即停用", "应复核", "需复核", "禁止",
    "不建议", "暂不推荐", "无明确", "未见明确", "需谨慎",
)


def emphasize_numbered(text: str) -> str:
    """管理端摘要用：常规重点加粗；含风险关键词的整条标红加粗（无表情）。"""
    t = emphasize_line(text)
    if any(w in t for w in _DANGER_WORDS):
        return f'<span style="color:#c62828;font-weight:700;">{t}</span>'
    return t


def render_numbered_html(items: list[str], *, title: str = "智能诊断摘要",
                         cls: str = "ag-rpt-current") -> str:
    """管理端摘要块：带序号（1./2./3.）、重点加粗、风险点标红、不含任何表情。"""
    if not items:
        return ""
    lis = "".join(f"<li>{emphasize_numbered(x)}</li>" for x in items)
    cls_attr = f"ag-rpt-advice-block {cls}".strip()
    head = (f'<div class="ag-rpt-advice-title"><span class="bullet"></span>{title}</div>'
            if title else "")
    return f'<div class="{cls_attr}">{head}<ol class="ag-rpt-brief">{lis}</ol></div>'


def emphasize_key_parts(text: str) -> str:
    """报告正文重点加粗：剂量/间隔期等数字 + 风险关键词（用 Markdown 粗体，交给渲染层处理）。"""
    out = []
    for ln in (text or "").splitlines():
        if ln.lstrip().startswith("#"):        # 标题已由渲染层加粗，不再叠加
            out.append(ln)
            continue
        t = _DOSE_RE.sub(lambda m: f"**{m.group(0)}**", ln)
        for w in _DANGER_WORDS:
            if w in t and f"**{w}**" not in t:
                t = t.replace(w, f"**{w}**")
        out.append(t)
    return "\n".join(out)


def number_sections(text: str) -> str:
    """给报告章节自动编号：一级章节 1. 2. 3.，子章节（1）（2）…（已有编号的不重复加）。"""
    out: list[str] = []
    n1 = n2 = 0
    for raw in (text or "").splitlines():
        m = re.match(r"^\s{0,3}(#{1,6})\s*(.+?)\s*$", raw)
        if not m:
            out.append(raw)
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        if re.match(r"^[（(]?\d+[）)、.]", title) or re.match(r"^[一二三四五六七八九十]+、", title):
            out.append(raw)
            continue
        if level <= 3:
            n1 += 1
            n2 = 0
            out.append(f"{m.group(1)} {n1}. {title}")
        else:
            n2 += 1
            out.append(f"{m.group(1)} （{n2}）{title}")
    return "\n".join(out)


def format_report_for_review(content: str) -> str:
    """管理端完整报告格式化：章节编号 + 重点加粗（药剂/剂量/风险词）。"""
    return number_sections(emphasize_key_parts(content))
