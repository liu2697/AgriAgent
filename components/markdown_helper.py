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


def strip_code_fence(text: str) -> str:
    """去掉 Markdown 代码围栏标记（```lang / ```），保留围栏内的正文。

    为什么需要：模型常把整篇回复包在代码围栏里。不清掉的话，
    围栏那一行会以字面量形式出现在页面/导出文件里（实测踩过：
    方案里出现了一行「```markdown」）。
    注意 `plan_plain_text` 走的是 `strip_md`，不是 `normalize_md`，
    因此这一步必须能被两处共用，否则纯文本导出仍会残留围栏。
    """
    if not text:
        return ""
    return re.sub(r"^[ \t]*`{3,}[a-zA-Z0-9_+-]*[ \t]*$", "", text,
                  flags=re.MULTILINE)


def strip_md(text: str) -> str:
    """去除 Markdown 符号与 emoji，输出逐行纯文本。"""
    if not text:
        return ""
    t = strip_emoji(strip_code_fence(text))
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)                      # 标题符
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)                                    # 加粗
    t = re.sub(r"\*(.+?)\*", r"\1", t)                                        # 斜体
    t = re.sub(r"`(.+?)`", r"\1", t)                                          # 行内代码
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                            # 链接
    t = re.sub(r"^>\s?", "", t, flags=re.MULTILINE)                           # 引用符
    t = re.sub(r"^-{3,}\s*$", "", t, flags=re.MULTILINE)                      # 分隔线
    t = re.sub(r"^\|.*\|\s*$", "", t, flags=re.MULTILINE)                     # 表格行
    t = re.sub(r"^\s*(?:[-*+•]|\d+[.、)])\s*", "", t, flags=re.MULTILINE)     # 列表/编号符
    # 句内残留记号：模型常在句子里引用标题（"### 1. 观察到的症状"）或留下落单星号，
    # 不去掉就会在页面/导出文件里露出 # 与 *（用户反馈）。
    t = re.sub(r"#{1,6}\s*", "", t)
    t = re.sub(r"\*+", "", t)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    return "\n".join(lines)


__all__ = [
    "strip_emoji", "strip_code_fence", "strip_md", "normalize_md", "md_to_html",
    "plan_html", "plan_plain_text", "plain_report_html",
]


def normalize_md(text: str) -> str:
    """把大模型输出的 Markdown 规范化为可安全渲染的形式。

    为什么需要它（实测踩过的坑）：
      模型常输出「1 空格缩进 + 编号」的列表，例如
          ## 第1周（10.04-10.10）
            1. **割秧晒田**：…
      Streamlit 渲染时会出现两类问题：
        1. 缩进列表可能被当成代码块 → 整行原样显示，`#`、`*` 全部露出；
        2. `**加粗**` 若跨行未闭合，Markdown 不认，`**` 变成字面量。
      实测效果就是用户看到的"井号星号没去掉、页面很难看"。

    因此本函数**只是规范化排版结构，不删内容**：
      - 去掉 ```` ```markdown ```` 代码围栏（模型常把整篇回复包在围栏里，
        若不清掉，围栏那行会以字面量形式出现在页面上 —— 实测踩过）
      - `### 标题` → 加粗独立成行（标题符去掉，层级靠空行与加粗体现）
      - 列表/编号行去掉前导缩进（消除被当代码块的风险）
      - 跨行未闭合的 `**` / `*` 成对清理
      - 压缩连续空行
    """
    if not text:
        return ""
    t = strip_code_fence(strip_emoji(text).replace("\r\n", "\n").replace("\r", "\n"))

    # 1) 标题行：去掉 # 号，保留文字并加粗，前后留空行便于分块
    t = re.sub(r"^[ \t]*#{1,6}[ \t]*(.+?)[ \t]*$", r"\n**\1**\n",
               t, flags=re.MULTILINE)

    # 2) 列表 / 编号行：去掉前导缩进（关键：防止被当代码块）
    t = re.sub(r"^[ \t]+(?=(?:[-*+•]|\d+[.、)])\s+)", "", t, flags=re.MULTILINE)

    # 3) 跨行未闭合的加粗：按整行成对处理，落单的直接去掉标记
    lines = []
    for ln in t.splitlines():
        if ln.count("**") % 2 == 1:
            ln = ln.replace("**", "")
        lines.append(ln)
    t = "\n".join(lines)

    # 4) 压缩 3 个以上连续空行为 1 个空行
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def md_to_html(text: str, title: str = "") -> str:
    """把 Markdown 方案渲染成**可直接用浏览器打开**的独立 HTML 文档。

    用途：导出给农技员/农户看的成品。选择 HTML 而不是 PDF 的原因：
    HTML 不需要额外依赖（PDF 需要 wkhtmltopdf/weasyprint 等），
    浏览器打开后可自行"打印为 PDF"，效果等同且零依赖。
    """
    body = html.escape(normalize_md(text))
    # 先转义再替换，保证注入安全（内容全部来自模型输出，不可信任）
    body = re.sub(r"^\*\*(.+?)\*\*$", r"<h3>\1</h3>", body, flags=re.MULTILINE)
    body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)
    # 注意：必须同时补上 </li>，否则后面的 <ul> 包裹正则匹配不到（实测踩过）
    body = re.sub(r"^\s*\d+[.、)]\s+(.+)$", r"<li>\1</li>", body, flags=re.MULTILINE)
    body = re.sub(r"^\s*[-*+•]\s+(.+)$", r"<li>\1</li>", body, flags=re.MULTILINE)
    # 连续 li 包一层 ul
    body = re.sub(r"(?:<li>.*?</li>\n?)+",
                  lambda m: "<ul>" + m.group(0).replace("\n", "") + "</ul>\n",
                  body, flags=re.S)
    body = body.replace("\n", "<br>\n")
    safe_title = html.escape(title or "农智链 AgriAgent 生产管理方案")
    return (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<title>{safe_title}</title><style>"
        "body{font-family:-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;"
        "max-width:820px;margin:2.5rem auto;padding:0 1.2rem;line-height:1.9;color:#263238;}"
        "h1{font-size:1.45rem;border-left:4px solid #1F6B45;padding-left:.6rem;}"
        "h3{font-size:1.02rem;color:#1f5f3a;margin:1.4rem 0 .4rem;}"
        "ul{margin:.3rem 0 .8rem;padding-left:1.4rem;}li{margin-bottom:.25rem;}"
        "strong{color:#0d5c63;}"
        "</style></head><body>"
        f"<h1>{safe_title}</h1>{body}</body></html>"
    )


def plan_html(text: str) -> str:
    """把生产方案 Markdown 渲染为应用内 HTML（去掉 # 与 *，按周分卡片）。

    与 `plain_report_html` 的区别：那个是"逐行纯文本"，这里是**结构化排版**：
      - 以「第N周 / 阶段」这类加粗小标题分组，每组一张卡片
      - 编号条目转成列表
    这样方案看起来是一份计划表，而不是一坨文字。
    """
    # 归一化全角/特殊星号（模型偶尔输出 ＊＊ / ∗∗ / ✱），否则下面的加粗识别匹配不到，
    # 页面上就会露出星号（用户实测：生长计划标题旁边出现 **第1周…**）。
    text = (text or "")
    for ch in ("＊", "∗", "✱", "✳", "✽", "❋"):
        text = text.replace(ch, "*")
    norm = normalize_md(text)
    if not norm:
        return '<div class="ag-plan-empty">（方案内容为空）</div>'

    # 首个加粗行作为总标题，其余加粗行作为分组小标题
    blocks: list[tuple[str, list[str]]] = [("", [])]
    for raw in norm.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = re.fullmatch(r"\*\*(.+?)\*\*", line)
        if m:
            blocks.append((m.group(1), []))
            continue
        blocks[-1][1].append(line)

    parts: list[str] = []
    for title, items in blocks:
        if not items and not title:
            continue
        rows = []
        for it in items:
            it = re.sub(r"^\s*\d+[.、)]\s+", "", it)
            # 列表符只在「符号 + 空格」时才算列表符。
            # 不能用 `[-*+•]\s*`：`\s*` 允许零个空格，会把 `**加粗**` 的第一个
            # 星号当成列表符吃掉，结果渲染成 `*加粗**`（实测踩过）。
            it = re.sub(r"^\s*[-+•]\s+", "", it)
            it = re.sub(r"^\s*[*]\s+", "", it)
            it = html.escape(it)
            it = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", it)
            # 兜底：转换后仍有落单星号/井号时直接去掉，页面上绝不显示记号
            it = re.sub(r"\*+", "", it)
            it = re.sub(r"#{1,6}\s*", "", it)
            rows.append(f"<li>{it}</li>")
        list_html = f"<ul>{''.join(rows)}</ul>" if rows else ""
        if title:
            title = re.sub(r"[*#]+", "", title).strip()
            parts.append(
                '<div class="ag-plan-block">'
                f'<div class="ag-plan-block-title">{html.escape(title)}</div>'
                f'{list_html}</div>'
            )
        elif list_html:
            parts.append(f'<div class="ag-plan-block">{list_html}</div>')
    return f'<div class="ag-plan">{"".join(parts)}</div>'


def plan_plain_text(text: str) -> str:
    """把方案转成去掉所有 Markdown 符号的纯文本（用于复制/粘贴或记事本查看）。"""
    return strip_md(text)


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
