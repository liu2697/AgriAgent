"""【未启用】页面滚动复位 —— 已按用户要求回退。

本文件目前**不再被任何代码引用**，保留仅为占位（沙箱不允许删除文件）。

## 背景

Streamlit 是单页应用：切换侧边栏功能页只重新执行脚本、替换主区域内容，
浏览器不重新加载页面，因此滚动位置被沿用 —— 表现为
「上一个功能页翻到底，切到下一个功能页后仍停在底部」。

曾尝试的解法：用一段零高度组件（`st.components.v1.html`）注入脚本，
把滚动容器（`[data-testid="stAppViewContainer"]` 等）复位到顶部。
Streamlit 1.64 没有提供滚动控制的 Python API，只能这样从浏览器端处理。

## 为什么撤掉

用户决定不改这一处，故 `app.py` 中已移除 `scroll_to_top()` 调用与相关 import。
现有实现已清空为下面的空操作，**不会产生任何副作用**。

## 如果以后要恢复

需要恢复的要点（原实现已验证可注入、页面不报错，但**未能在真实浏览器中
确认滚动效果**）：

1. 必须在 `window.parent.document` 上操作：组件渲染在同源 iframe 内，
   直接查 `document` 只能查到高度为 0 的 iframe 自身；
2. 同时复位多个候选容器并兜底文档级滚动，各版本/主题下真正滚动的元素不同；
3. 复位时机放在 `requestAnimationFrame` 之后并补一次延迟调用，
   否则会在内容替换前滚动，等于没滚；
4. 组件 `height=0`，不占布局。

恢复步骤：把下面的函数体换成原实现，并在 `app.py` 的 `inject_theme()`
之后调用 `scroll_to_top()`。
"""
from __future__ import annotations


def scroll_to_top() -> None:
    """空操作。原滚动复位实现已按用户要求移除，详见模块文档。"""
    return None


__all__ = ["scroll_to_top"]
