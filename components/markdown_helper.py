"""Markdown 报告 → 纯文本 HTML 渲染辅助。"""
import html
import re

# emoji 及装饰符号范围（表情、杂项符号、区域指示符、变体选择符、零宽连接符等）
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000200D"
    "\U0001F900-\U0001F9FF]"
)


def strip_emoji(text: str) -> str:
    """移除文本中的全部 emoji 与装饰符号。"""
    if not text:
        return ""
    return _EMOJI_RE.sub("", text)


def strip_md(text: str) -> str:
    """去除 Markdown 符号与 emoji，输出逐行纯文本。"""
    if not text:
        return ""
    t = strip_emoji(text)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)                      # 标题符
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)                                    # 加粗
    t = re.sub(r"\*(.+?)\*", r"\1", t)                                        # 斜体
    t = re.sub(r"`(.+?)`", r"\1", t)                                          # 行内代码
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                            # 链接
    t = re.sub(r"^>\s?", "", t, flags=re.MULTILINE)                           # 引用符
    t = re.sub(r"^-{3,}\s*$", "", t, flags=re.MULTILINE)                      # 分隔线
    t = re.sub(r"^\|.*\|\s*$", "", t, flags=re.MULTILINE)                     # 表格行
    t = re.sub(r"^\s*(?:[-*+•]|\d+[.、)])\s*", "", t, flags=re.MULTILINE)     # 列表/编号符
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    return "\n".join(lines)


def plain_report_html(text: str, css_class: str = "ag-plain-report") -> str:
    """将诊断内容渲染为无 Markdown 符号、HTML 安全的纯文本块。"""
    plain = strip_md(text)
    safe = html.escape(plain) if plain else "（无诊断内容）"
    return (
        f'<div class="{css_class}" style="white-space:pre-wrap;'
        f'font-size:0.85rem;line-height:1.9;color:#455a64;'
        f'padding:0.85rem 1rem;background:#f8fafc;'
        f'border:1px solid #e2e8f0;border-radius:4px;">'
        f'{safe}</div>'
    )
