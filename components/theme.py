"""
统一主题系统。

设计方向：农业数字化 SaaS 后台 / 政府农业监管系统
- 无大面积渐变 Banner
- 深绿 + 深青为主色调，避免荧光绿
- 中性色采用灰蓝，标题专业稳重
- 圆角 4px，阴影极淡（硬派表格和卡片风格）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Theme:
    """全局主题 Token。"""

    brand: str = "#1F6B45"          # 主色（深绿）
    brand_hover: str = "#174a2c"
    brand_light: str = "#e8f1ec"    # 浅绿底
    accent: str = "#0d5c63"         # 辅助色（深青）

    success: str = "#2e7d32"
    success_bg: str = "#e8f5e9"

    warning: str = "#e67e22"
    warning_bg: str = "#fff3e0"

    danger: str = "#c0392b"
    danger_bg: str = "#ffebee"

    info: str = "#1976d2"
    info_bg: str = "#e3f2fd"

    neutral: str = "#2c3e50"        # 深灰蓝（标题）
    neutral_2: str = "#546e7a"      # 次级标题
    neutral_3: str = "#78909c"      # 正文
    neutral_4: str = "#b0bec5"      # 辅助说明
    neutral_5: str = "#cfd8dc"      # 边框色

    bg_page: str = "#f5f7fa"        # 页面底色
    bg_card: str = "#ffffff"        # 卡片底色
    bg_strip: str = "#f8fafc"       # 表格条纹

    text_primary: str = "#1a2632"
    text_secondary: str = "#546e7a"
    text_muted: str = "#90a4ae"

    border_radius: str = "4px"
    border_radius_lg: str = "6px"
    shadow_sm: str = "0 1px 2px rgba(0,0,0,0.04)"
    shadow_md: str = "0 2px 6px rgba(0,0,0,0.06)"

    font_family: str = "-apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"

    def as_dict(self) -> Dict[str, str]:
        return {k: v for k, v in self.__dict__.items()}


DEFAULT_THEME = Theme()


def build_css(theme: Theme = DEFAULT_THEME) -> str:
    """根据主题 Token 生成注入 Streamlit 的全局 CSS。"""
    t = theme

    css_vars = "\n".join(f"    --ag-{k}: {v};" for k, v in t.as_dict().items())

    return f"""
<style>
:root {{
{css_vars}
}}

/* -------- 基础排版 -------- */
.stApp {{
    background-color: {t.bg_page};
    font-family: {t.font_family};
    color: {t.text_primary};
}}

.block-container {{
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}}

/* 隐藏 Streamlit 默认的 gradient header */
[data-testid="stHeader"] {{
    background: transparent !important;
    box-shadow: none !important;
}}

/* -------- 侧边栏 -------- */
[data-testid="stSidebar"] {{
    background-color: #ffffff;
    border-right: 1px solid {t.neutral_5};
    padding-top: 1.2rem;
}}
[data-testid="stSidebarNav"] {{
    padding-top: 0.5rem;
}}

/* -------- 标题层 -------- */
h1, h2, h3, h4, h5, h6 {{
    color: {t.neutral} !important;
    font-weight: 600;
    letter-spacing: -0.01em;
}}
h1 {{ font-size: 1.75rem !important; }}
h2 {{ font-size: 1.35rem !important; }}
h3 {{ font-size: 1.12rem !important; }}
h4 {{ font-size: 0.98rem !important; }}

.stMarkdown p {{
    color: {t.text_primary};
    line-height: 1.65;
}}

.stCaption {{
    color: {t.text_muted};
    font-size: 0.82rem;
}}

/* -------- 按钮 -------- */
.stButton > button,
.stDownloadButton > button {{
    border-radius: {t.border_radius} !important;
    border: 1px solid {t.neutral_5} !important;
    background-color: #ffffff !important;
    color: {t.neutral} !important;
    font-weight: 500 !important;
    height: 2.2rem;
    transition: all .15s;
    box-shadow: none !important;
}}
.stButton > button:hover,
.stDownloadButton > button:hover {{
    border-color: {t.brand} !important;
    color: {t.brand} !important;
    background-color: {t.brand_light} !important;
}}
.stButton > button[kind="primary"] {{
    background-color: {t.brand} !important;
    border-color: {t.brand} !important;
    color: #ffffff !important;
}}
.stButton > button[kind="primary"]:hover {{
    background-color: {t.brand_hover} !important;
    border-color: {t.brand_hover} !important;
}}

/* -------- 卡片 -------- */
.ag-card {{
    background: {t.bg_card};
    border: 1px solid {t.neutral_5};
    border-radius: {t.border_radius_lg};
    padding: 1.25rem 1.5rem;
    box-shadow: {t.shadow_sm};
    margin-bottom: 0.75rem;
}}
.ag-card-header {{
    font-size: 0.8rem;
    font-weight: 600;
    color: {t.text_muted};
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.35rem;
}}
.ag-card-value {{
    font-size: 1.65rem;
    font-weight: 700;
    color: {t.neutral};
    letter-spacing: -0.02em;
}}
.ag-card-trend {{
    font-size: 0.78rem;
    margin-top: 0.35rem;
    color: {t.text_muted};
}}

/* -------- 徽章 -------- */
.ag-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    line-height: 1.4;
}}
.ag-badge-success {{ background: {t.success_bg}; color: {t.success}; }}
.ag-badge-warning {{ background: {t.warning_bg}; color: {t.warning}; }}
.ag-badge-danger  {{ background: {t.danger_bg};  color: {t.danger}; }}
.ag-badge-info    {{ background: {t.info_bg};    color: {t.info}; }}
.ag-badge-muted   {{ background: {t.bg_strip};    color: {t.neutral_3}; }}

/* -------- 分隔线 -------- */
hr, .stDivider {{
    border-color: {t.neutral_5};
    margin: 1.2rem 0;
}}

/* -------- Metric -------- */
[data-testid="stMetric"] {{
    background: {t.bg_card};
    border: 1px solid {t.neutral_5};
    border-radius: {t.border_radius};
    padding: 0.9rem 1rem;
}}
[data-testid="stMetricLabel"] {{
    color: {t.text_muted};
    font-size: 0.78rem;
    font-weight: 500;
}}
[data-testid="stMetricValue"] {{
    color: {t.neutral} !important;
    font-weight: 700;
}}

/* -------- DataFrame / 表格 -------- */
.stDataFrame {{
    border: 1px solid {t.neutral_5};
    border-radius: {t.border_radius};
    overflow: hidden;
}}

/* -------- Expander -------- */
.streamlit-expanderHeader {{
    font-weight: 500;
    color: {t.neutral};
    border-radius: {t.border_radius} !important;
}}
.streamlit-expander {{
    border: 1px solid {t.neutral_5};
    border-radius: {t.border_radius};
    margin-bottom: 0.5rem;
}}

/* -------- Status / Progress -------- */
[data-testid="stStatusWidget"] {{
    border: 1px solid {t.neutral_5};
    border-radius: {t.border_radius};
}}

/* -------- Selectbox / Input -------- */
.stSelectbox > div > div,
.stTextInput > div > div,
.stTextArea > div > div,
.stNumberInput > div > div {{
    border-radius: {t.border_radius} !important;
    border-color: {t.neutral_5} !important;
}}
.stSelectbox > div > div:focus-within,
.stTextInput > div > div:focus-within,
.stTextArea > div > div:focus-within {{
    border-color: {t.brand} !important;
    box-shadow: 0 0 0 2px rgba(31, 95, 58, 0.12) !important;
}}

/* -------- 页面头部区 -------- */
.ag-page-header {{
    padding: 1rem 0 0.75rem 0;
    margin-bottom: 1rem;
    border-bottom: 1px solid {t.neutral_5};
}}
.ag-page-title {{
    font-size: 1.35rem;
    font-weight: 700;
    color: {t.neutral};
    margin: 0;
    letter-spacing: -0.02em;
}}
.ag-page-sub {{
    font-size: 0.85rem;
    color: {t.text_muted};
    margin-top: 0.25rem;
}}

/* -------- Section header -------- */
.ag-section-title {{
    font-size: 0.95rem;
    font-weight: 600;
    color: {t.neutral};
    margin: 1.5rem 0 0.75rem 0;
    padding-left: 0.6rem;
    border-left: 3px solid {t.brand};
}}

/* -------- 风险等级色板 -------- */
.ag-risk-high {{ color: {t.danger}; }}
.ag-risk-mid  {{ color: {t.warning}; }}
.ag-risk-low  {{ color: {t.info}; }}
.ag-risk-none {{ color: {t.success}; }}

/* -------- 工单 / 步骤状态 -------- */
.ag-step {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.4rem 0.6rem;
    border-radius: {t.border_radius};
    margin-bottom: 0.25rem;
    font-size: 0.85rem;
    border-left: 3px solid {t.neutral_5};
    background: {t.bg_card};
}}
.ag-step.done    {{ border-left-color: {t.success}; }}
.ag-step.running {{ border-left-color: {t.info};    background: {t.info_bg}; }}
.ag-step.failed  {{ border-left-color: {t.danger};  background: {t.danger_bg}; }}
.ag-step.skipped {{ border-left-color: {t.neutral_4}; }}

/* -------- 地块卡 -------- */
.ag-plot-card {{
    background: {t.bg_card};
    border: 1px solid {t.neutral_5};
    border-radius: {t.border_radius_lg};
    padding: 1rem 1.25rem;
    margin-bottom: 0.6rem;
    box-shadow: {t.shadow_sm};
}}
.ag-plot-card:hover {{
    border-color: {t.brand};
    box-shadow: {t.shadow_md};
}}

/* -------- 隐藏 Streamlit default "running" spinner -------- */
.stSpinner {{ display: none; }}

/* -------- Agent 可视化：任务分析 -------- */
.ag-agent-insight {{
    background: {t.brand_light};
    border-left: 3px solid {t.brand};
    padding: 0.65rem 0.9rem;
    border-radius: {t.border_radius};
    font-size: 0.84rem;
    color: {t.neutral};
    margin: 0.4rem 0;
    line-height: 1.7;
}}

.ag-agent-table th,
.ag-agent-table td {{
    font-size: 0.82rem;
}}
.ag-agent-table tr.ag-step-done {{ background: {t.success_bg}; }}
.ag-agent-table tr.ag-step-running {{ background: {t.info_bg}; }}
.ag-agent-table tr.ag-step-failed {{ background: {t.danger_bg}; }}
.ag-agent-table tr.ag-step-skipped {{ color: {t.neutral_4}; }}
.ag-agent-table tr.ag-step-pending {{ color: {t.neutral_4}; }}

.ag-status-done {{ color: {t.success}; font-weight: 600; font-size: 0.78rem; }}
.ag-status-running {{ color: {t.info}; font-weight: 600; font-size: 0.78rem; }}
.ag-status-failed {{ color: {t.danger}; font-weight: 600; font-size: 0.78rem; }}
.ag-status-skipped {{ color: {t.neutral_4}; font-size: 0.78rem; }}
.ag-status-pending {{ color: {t.neutral_4}; font-size: 0.78rem; }}

/* -------- Agent 可视化：工具调用卡片 -------- */
.ag-tools-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 0.65rem;
    margin-top: 0.5rem;
}}
.ag-tool-card {{
    background: {t.bg_card};
    border: 1px solid {t.neutral_5};
    border-radius: {t.border_radius_lg};
    padding: 0.85rem 1rem;
    box-shadow: {t.shadow_sm};
    font-size: 0.82rem;
}}

.ag-chip {{
    display: inline-block;
    padding: 1px 7px;
    background: {t.bg_strip};
    border: 1px solid {t.neutral_5};
    border-radius: 4px;
    font-size: 0.7rem;
    color: {t.neutral_3};
    font-weight: 500;
}}

.ag-badge-done {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    background: {t.success_bg};
    color: {t.success};
}}
.ag-badge-running {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    background: {t.info_bg};
    color: {t.info};
}}
.ag-badge-failed {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    background: {t.danger_bg};
    color: {t.danger};
}}
.ag-badge-skipped {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    background: {t.bg_strip};
    color: {t.neutral_3};
}}
.ag-badge-pending {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    background: {t.bg_strip};
    color: {t.neutral_4};
}}

/* -------- Agent 可视化：可信度评分 -------- */
.ag-score-ring {{
    text-align: center;
    padding: 0.8rem 0;
}}
.ag-score-num {{
    font-size: 3rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.03em;
}}
.ag-score-unit {{
    font-size: 0.95rem;
    color: {t.neutral_4};
    margin-top: -0.2rem;
}}
.ag-score-label {{
    font-size: 0.78rem;
    color: {t.neutral_3};
    margin-top: 0.1rem;
    font-weight: 500;
}}
.ag-score-breakdown {{
    font-size: 0.82rem;
    color: {t.neutral_3};
    line-height: 1.7;
    padding: 0.3rem 0;
    margin-bottom: 0.5rem;
}}

/* -------- scrollbar -------- */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{
    background: {t.neutral_5};
    border-radius: 4px;
}}
::-webkit-scrollbar-thumb:hover {{ background: {t.neutral_4}; }}

/* ==========================================================
 * 农智链 AgriAgent — Agent 工作流决策过程（政务科技风）
 * ========================================================== */
.ag-flow {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 0.9rem 0.9rem 0.6rem;
    margin: 0.4rem 0 0.8rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}}
.ag-flow-title {{
    font-size: 0.92rem;
    font-weight: 700;
    color: {t.neutral};
    margin: 0 0 0.15rem 0;
    display: flex;
    align-items: center;
    gap: 0.45rem;
}}
.ag-flow-title-bar {{
    width: 3px;
    height: 1rem;
    background: {t.brand};
    border-radius: 2px;
    flex-shrink: 0;
}}
.ag-flow-sub {{
    font-size: 0.72rem;
    color: #90a4ae;
    margin-bottom: 0.7rem;
}}
.ag-flow-step {{
    background: #ffffff;
    border: 1px solid #e8edf2;
    border-left: 3px solid #cfd8dc;
    border-radius: 4px;
    padding: 0.6rem 0.75rem;
    margin-bottom: 0.35rem;
    position: relative;
}}
.ag-flow-step.done {{ border-left-color: {t.brand}; background: #f6faf7; }}
.ag-flow-step.running {{ border-left-color: {t.info}; background: #eaf6fb; }}
.ag-flow-step.failed {{ border-left-color: {t.danger}; background: #fdecea; }}
.ag-flow-step.skipped {{ border-left-color: #cfd8dc; background: #f8fafc; opacity: 0.75; }}
.ag-flow-step.pending {{ border-left-color: #cfd8dc; }}

.ag-flow-head {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.35rem;
}}
.ag-flow-icon {{
    flex-shrink: 0;
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.95rem;
    background: #f1f5f9;
    color: #78909c;
}}
.ag-flow-step.done .ag-flow-icon    {{ background: {t.brand_light}; color: {t.brand}; }}
.ag-flow-step.running .ag-flow-icon {{ background: #e3f2fd; color: {t.info};  }}
.ag-flow-step.failed .ag-flow-icon  {{ background: {t.danger_bg}; color: {t.danger}; }}
.ag-flow-step.skipped .ag-flow-icon {{ background: #f1f5f9; color: #b0bec5; }}

.ag-flow-name {{
    flex: 1;
    min-width: 0;
}}
.ag-flow-name-main {{
    font-size: 0.84rem;
    font-weight: 600;
    color: #2c3e50;
    line-height: 1.25;
}}
.ag-flow-name-sub {{
    font-size: 0.68rem;
    color: #90a4ae;
    margin-top: 0.05rem;
}}
.ag-flow-status {{
    flex-shrink: 0;
    font-size: 0.68rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    line-height: 1.3;
}}
.ag-flow-status.done    {{ background: {t.success_bg}; color: {t.success}; }}
.ag-flow-status.running {{ background: #e3f2fd; color: {t.info}; }}
.ag-flow-status.failed  {{ background: {t.danger_bg}; color: {t.danger}; }}
.ag-flow-status.skipped {{ background: #f1f5f9; color: #90a4ae; }}
.ag-flow-status.pending {{ background: #f1f5f9; color: #b0bec5; }}

.ag-flow-body {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.45rem;
}}
.ag-flow-io {{
    background: #f8fafc;
    border-radius: 5px;
    padding: 0.35rem 0.5rem;
    font-size: 0.72rem;
    line-height: 1.55;
    border: 1px solid #eef2f6;
}}
.ag-flow-io-lbl {{
    font-size: 0.6rem;
    font-weight: 600;
    color: #90a4ae;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.12rem;
}}
.ag-flow-io-val {{
    color: #546e7a;
    font-size: 0.74rem;
    word-break: break-all;
}}
.ag-flow-io-val.ok   {{ color: {t.brand}; font-weight: 500; }}
.ag-flow-io-val.warn {{ color: {t.warning}; }}
.ag-flow-io-val.err  {{ color: {t.danger}; }}
.ag-flow-io-val.note {{ color: #b0bec5; font-style: italic; }}

.ag-flow-arrow {{
    text-align: center;
    margin: 0.2rem 0 0.1rem;
    font-size: 0.8rem;
    color: #b0bec5;
    line-height: 1;
}}
.ag-flow-final {{
    margin-top: 0.55rem;
    background: {t.brand};
    border-radius: 6px;
    padding: 0.75rem 0.9rem;
    color: #fff;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
}}
.ag-flow-final-txt {{
    font-size: 0.86rem;
    font-weight: 600;
    flex: 1;
    min-width: 0;
}}
.ag-flow-final-sub {{
    font-size: 0.7rem;
    opacity: 0.85;
    margin-top: 0.1rem;
}}

/* ==========================================================
 * 农智链 AgriAgent — 智能体执行过程（比赛展示用）
 * ========================================================== */
.ag-exec-wrap {{
    background: #ffffff;
    border-radius: 6px;
    padding: 1.1rem 1.15rem 1.0rem;
    margin: 0.4rem 0 0.9rem;
    border: 1px solid #e0ece4;
}}
.ag-exec-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.7rem;
    margin-bottom: 0.9rem;
    padding-bottom: 0.7rem;
    border-bottom: 1.5px solid #e4ecf0;
}}
.ag-exec-header-left {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
}}
.ag-exec-header-icon {{
    font-size: 1.5rem;
    width: 2.6rem; height: 2.6rem;
    display: flex; align-items: center; justify-content: center;
    background: {t.brand};
    border-radius: 6px;
    color: #fff;
}}
.ag-exec-header-main {{
    font-size: 1.05rem;
    font-weight: 700;
    color: #1f3b2d;
    letter-spacing: 0.01em;
}}
.ag-exec-header-sub {{
    font-size: 0.72rem;
    color: #78909c;
    font-family: "SF Mono", "JetBrains Mono", "Menlo", monospace;
    margin-top: 0.1rem;
}}
.ag-exec-header-stats {{
    display: flex;
    gap: 0.5rem;
}}
.ag-exec-stat {{
    background: #fff;
    border: 1px solid #e0ece4;
    border-radius: 4px;
    padding: 0.35rem 0.65rem;
    text-align: center;
    min-width: 3rem;
}}
.ag-exec-stat .num {{
    display: block;
    font-size: 1.15rem;
    font-weight: 800;
    color: {t.brand};
    line-height: 1.1;
}}
.ag-exec-stat .lbl {{
    display: block;
    font-size: 0.66rem;
    color: #90a4ae;
    margin-top: 0.05rem;
}}

.ag-exec-cards {{
    display: flex;
    flex-direction: column;
    gap: 0;
}}
.ag-exec-arrow {{
    text-align: center;
    color: #b0bec5;
    font-size: 0.85rem;
    line-height: 0.6;
    margin: -0.25rem 0 0;
}}

.ag-exec-card {{
    position: relative;
    background: #fff;
    border: 1.5px solid #e6ecef;
    border-radius: 4px;
    padding: 0.7rem 0.85rem;
    margin-bottom: 0.35rem;
    border-left: 4px solid #cfd8dc;
    transition: box-shadow 0.2s, transform 0.15s;
}}
.ag-exec-card:hover {{
    box-shadow: none;
}}
.ag-exec-card.done {{
    border-left-color: {t.brand};
    background: #f8fcf9;
}}
.ag-exec-card.running {{
    border-left-color: {t.info};
    background: #f2f9fd;
}}
.ag-exec-card.failed {{
    border-left-color: {t.danger};
    background: #fff3f0;
}}
.ag-exec-card.skipped {{
    border-left-color: #b0bec5;
    background: #f8fafc;
    opacity: 0.78;
}}
.ag-exec-card.pending {{
    border-left-color: #cfd8dc;
}}

.ag-exec-idx {{
    position: absolute;
    top: -0.4rem;
    left: 0.5rem;
    background: #fff;
    padding: 0 0.4rem;
    font-size: 0.62rem;
    font-weight: 700;
    color: #b0bec5;
    letter-spacing: 0.05em;
}}
.ag-exec-card.done .ag-exec-idx {{ color: {t.brand}; }}
.ag-exec-card.failed .ag-exec-idx {{ color: {t.danger}; }}

.ag-exec-head {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.4rem;
}}
.ag-exec-icon {{
    width: 2.2rem; height: 2.2rem;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.05rem;
    background: #edf5ef;
    border-radius: 4px;
    flex-shrink: 0;
    transition: all 0.2s;
}}
.ag-exec-card.done .ag-exec-icon {{
    background: {t.brand_light};
    color: {t.brand};
}}
.ag-exec-card.running .ag-exec-icon {{
    background: #e3f2fd;
    color: {t.info};
    
}}
.ag-exec-card.failed .ag-exec-icon {{
    background: {t.danger_bg};
    color: {t.danger};
}}
.ag-exec-card.skipped .ag-exec-icon {{
    background: #f1f5f9;
    color: #b0bec5;
}}

.ag-exec-title-wrap {{
    flex: 1;
    min-width: 0;
}}
.ag-exec-title {{
    font-size: 0.88rem;
    font-weight: 700;
    color: #1f3b2d;
    line-height: 1.25;
}}
.ag-exec-sub {{
    font-size: 0.66rem;
    color: #90a4ae;
    font-family: "SF Mono", "JetBrains Mono", monospace;
    margin-top: 0.05rem;
}}

.ag-exec-status {{
    font-size: 0.68rem;
    font-weight: 600;
    padding: 0.18rem 0.55rem;
    border-radius: 4px;
    flex-shrink: 0;
    white-space: nowrap;
}}
.ag-exec-status.done {{
    background: {t.success_bg};
    color: {t.success};
}}
.ag-exec-status.running {{
    background: #e3f2fd;
    color: {t.info};
}}
.ag-exec-status.failed {{
    background: {t.danger_bg};
    color: {t.danger};
}}
.ag-exec-status.skipped {{
    background: #f1f5f9;
    color: #90a4ae;
}}
.ag-exec-status.pending {{
    background: #f1f5f9;
    color: #b0bec5;
}}

.ag-exec-module {{
    font-size: 0.68rem;
    color: #78909c;
    margin-bottom: 0.4rem;
    font-family: "SF Mono", "JetBrains Mono", monospace;
}}
.ag-exec-mod-tag {{
    display: inline-block;
    font-size: 0.56rem;
    font-weight: 700;
    color: #fff;
    background: #78909c;
    border-radius: 3px;
    padding: 0.05rem 0.3rem;
    margin-right: 0.35rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    font-family: inherit;
}}

.ag-exec-io {{
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}}
.ag-exec-io-row {{
    display: flex;
    gap: 0.55rem;
    align-items: flex-start;
}}
.ag-exec-io-lbl {{
    font-size: 0.64rem;
    font-weight: 700;
    color: #b0bec5;
    width: 2.1rem;
    flex-shrink: 0;
    text-align: right;
    padding-top: 0.12rem;
    letter-spacing: 0.04em;
}}
.ag-exec-io-val {{
    font-size: 0.78rem;
    color: #455a64;
    flex: 1;
    line-height: 1.45;
    word-break: break-all;
}}
.ag-exec-io-val.ok {{
    color: {t.brand};
    font-weight: 500;
}}
.ag-exec-io-val.err {{
    color: {t.danger};
}}
.ag-exec-io-val.note {{
    color: #b0bec5;
    font-style: italic;
}}

/* -------- 信息卡（标签 + 值，卡片化布局） -------- */
.ag-info-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
    margin: 0.4rem 0 0.7rem;
}}
.ag-info-card {{
    background: #ffffff;
    border: 1px solid #e4e9ef;
    border-radius: 6px;
    padding: 0.6rem 0.75rem;
}}
.ag-info-lbl {{
    font-size: 0.68rem;
    color: #90a4ae;
    margin-bottom: 0.2rem;
}}
.ag-info-val {{
    font-size: 0.95rem;
    font-weight: 600;
    color: #2c3e50;
    line-height: 1.3;
}}
@media only screen and (max-width: 768px) {{
    .ag-info-grid {{ grid-template-columns: repeat(2, 1fr); gap: 0.4rem; }}
    .ag-info-card {{ padding: 0.5rem 0.6rem; }}
    .ag-info-val {{ font-size: 0.85rem; }}
}}

/* -------- 业务流转步骤条 -------- */
.ag-fs {{ display: flex; align-items: center; flex-wrap: wrap; margin: 0.6rem 0; }}
.ag-fs-v {{ display: flex; flex-direction: column; align-items: flex-start; margin: 0.4rem 0; }}
.ag-fs-step {{ display: flex; align-items: center; gap: 0.3rem; }}
.ag-fs-dot {{
    width: 18px; height: 18px; border-radius: 3px;
    background: #f1f5f9; color: #90a4ae;
    font-size: 11px; font-weight: 600;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}}
.ag-fs-dot.done {{ background: {t.brand}; color: #fff; }}
.ag-fs-dot.current {{ background: #fff; color: {t.brand}; border: 1px solid {t.brand}; }}
.ag-fs-label {{ font-size: 0.76rem; color: #90a4ae; margin: 0 0.4rem 0 0.3rem; white-space: nowrap; }}
.ag-fs-label.done {{ color: #546e7a; }}
.ag-fs-label.current {{ color: {t.brand}; font-weight: 600; }}
.ag-fs-arrow {{ color: #cfd8dc; margin: 0 0.15rem; font-size: 0.8rem; }}
.ag-fs-v .ag-fs-arrow {{ margin: 0.12rem 0 0.12rem 0.55rem; line-height: 1; }}

/* -------- 分析流程（简单状态勾选） -------- */
.ag-flow-line {{
    display: flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.32rem 0.15rem;
    font-size: 0.82rem;
    color: #546e7a;
    border-bottom: 1px dashed #eef2f6;
}}
.ag-flow-line:last-child {{ border-bottom: none; }}
.ag-flow-mark {{
    width: 1.15rem;
    height: 1.15rem;
    border-radius: 3px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    background: #f1f5f9;
    color: #b0bec5;
    flex-shrink: 0;
}}
.ag-flow-line.done .ag-flow-mark {{ background: {t.success_bg}; color: {t.success}; }}
.ag-flow-line.skip .ag-flow-mark {{ background: #f1f5f9; color: #b0bec5; }}
.ag-flow-line.fail .ag-flow-mark {{ background: {t.danger_bg}; color: {t.danger}; }}
.ag-flow-line.done .ag-flow-name {{ color: {t.neutral}; font-weight: 500; }}
.ag-flow-line.skip .ag-flow-name {{ color: #b0bec5; }}

/* -------- 智能体执行流 —— 移动端单列优化 */
@media only screen and (max-width: 768px) {{
    .ag-exec-wrap {{ padding: 0.85rem 0.8rem 0.75rem; }}
    .ag-exec-header {{ margin-bottom: 0.7rem; padding-bottom: 0.55rem; }}
    .ag-exec-header-icon {{ width: 2rem; height: 2rem; font-size: 1.25rem; }}
    .ag-exec-header-main {{ font-size: 0.92rem; }}
    .ag-exec-header-sub {{ font-size: 0.62rem; }}
    .ag-exec-stat {{ padding: 0.25rem 0.5rem; min-width: 2.4rem; }}
    .ag-exec-stat .num {{ font-size: 0.98rem; }}
    .ag-exec-card {{ padding: 0.6rem 0.7rem; margin-bottom: 0.28rem; }}
    .ag-exec-title {{ font-size: 0.8rem; }}
    .ag-exec-sub {{ font-size: 0.58rem; }}
    .ag-exec-module {{ font-size: 0.6rem; }}
    .ag-exec-io-val {{ font-size: 0.7rem; }}
    .ag-exec-io-lbl {{ font-size: 0.56rem; width: 1.7rem; }}
}}

/* ==========================================================
 * 农智链 AgriAgent — AI 植保诊断报告（比赛截图专用）
 * ========================================================== */
.ag-rpt-header {{
    background: #ffffff;
    border: 1px solid {t.neutral_5};
    border-left: 4px solid {t.brand};
    border-radius: 4px;
    padding: 0.9rem 1.1rem;
    margin: 0.3rem 0 0.7rem;
    color: {t.neutral};
}}
.ag-rpt-hd-badge {{
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    color: #ffffff;
    background: {t.brand};
    padding: 2px 10px;
    border-radius: 3px;
    letter-spacing: 0.03em;
}}
.ag-rpt-hd-title {{
    font-size: 1.35rem;
    font-weight: 700;
    margin: 0.35rem 0 0.1rem;
    letter-spacing: 0.01em;
    color: {t.neutral};
}}
.ag-rpt-hd-sub {{
    font-size: 0.78rem;
    color: {t.neutral_3};
    line-height: 1.5;
    margin-bottom: 0.5rem;
}}
.ag-rpt-hd-tags {{
    display: flex;
    gap: 0.35rem;
    margin-top: 0.6rem;
    flex-wrap: wrap;
}}
.ag-rpt-hd-tag {{
    display: inline-block;
    padding: 2px 8px;
    background: #f1f5f9;
    color: {t.neutral_2};
    font-size: 0.72rem;
    border-radius: 3px;
    margin-right: 0.25rem;
}}

/* -------- 模块 -------- */
.ag-rpt-section {{
    background: #ffffff;
    border: 1px solid #e4e9ef;
    border-radius: 4px;
    padding: 0.9rem 1rem;
    margin: 0.5rem 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}}
.ag-rpt-sec-head {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.7rem;
    padding-bottom: 0.45rem;
    border-bottom: 1px solid #eef2f6;
}}
.ag-rpt-sec-bar {{
    width: 3px;
    height: 1.1rem;
    background: {t.brand};
    border-radius: 2px;
    flex-shrink: 0;
}}
.ag-rpt-sec-icon {{
    font-size: 1rem;
    line-height: 1;
}}
.ag-rpt-sec-title {{
    font-size: 0.92rem;
    font-weight: 700;
    color: {t.neutral};
    line-height: 1.2;
}}
.ag-rpt-sec-sub {{
    font-size: 0.68rem;
    color: #90a4ae;
    margin-left: auto;
}}

/* -------- 农户端步骤引导（拍照片 / 选作物 / 选症状）-------- */
.ag-step-guide {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.02rem;
    font-weight: 700;
    color: #1f5f3a;
    margin: 0.9rem 0 0.5rem 0;
}}
.ag-step-no {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    background: #1f5f3a;
    color: #fff;
    font-size: 0.85rem;
    font-weight: 700;
    flex: 0 0 auto;
}}

/* -------- 农户端结论区：病名最大化 -------- */
.ag-rpt-verdict {{
    padding: 0.35rem 0.2rem 0.2rem 0.2rem;
}}
.ag-rpt-verdict-name {{
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1.2;
    color: #14301f;
    letter-spacing: -0.01em;
    word-break: break-word;
}}
.ag-rpt-verdict-meta {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.4rem;
    font-size: 0.92rem;
    font-weight: 700;
}}
.ag-rpt-verdict-dim {{
    color: #b0bec5;
    font-weight: 400;
}}
.ag-rpt-verdict-advice {{
    margin-top: 0.45rem;
    font-size: 0.86rem;
    line-height: 1.55;
    color: #546e7a;
    background: #f8fafc;
    border-left: 3px solid #cfd8dc;
    border-radius: 4px;
    padding: 0.5rem 0.6rem;
}}

/* -------- 农户端「现在要做的事」 -------- */
.ag-act-list {{
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    margin-top: 0.45rem;
}}
.ag-act-item {{
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    background: #f5faf7;
    border: 1px solid #e2efe7;
    border-radius: 8px;
    padding: 0.6rem 0.7rem;
}}
.ag-act-no {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.6rem;
    height: 1.6rem;
    border-radius: 50%;
    background: #1f5f3a;
    color: #fff;
    font-size: 0.82rem;
    font-weight: 700;
    flex: 0 0 auto;
}}
.ag-act-text {{
    font-size: 0.95rem;
    line-height: 1.6;
    color: #263238;
    font-weight: 500;
}}

/* -------- 生长档案时间轴（原先样式内联在页面里，已上移集中管理） -------- */
.ag-tl {{
    border-left: 2px solid #cfd8dc;
    margin: 0.2rem 0 0.2rem 0.6rem;
    padding: 0.2rem 0 0.5rem 1.15rem;
}}
.ag-tl-item {{
    position: relative;
    padding-bottom: 0.55rem;
}}
.ag-tl-item:last-child {{ padding-bottom: 0; }}
.ag-tl-dot {{
    position: absolute;
    left: -1.45rem;
    top: 0.35rem;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: #1f5f3a;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1px #cfd8dc;
}}
.ag-tl-time {{
    font-size: 0.74rem;
    color: #90a4ae;
    line-height: 1.4;
}}
.ag-tl-title {{
    font-weight: 600;
    font-size: 0.88rem;
    color: #2c3e50;
    line-height: 1.5;
}}
.ag-tl-detail {{
    font-size: 0.82rem;
    color: #546e7a;
    line-height: 1.6;
}}

/* -------- 生产方案（结构化卡片：按周/阶段分组） -------- */
.ag-plan {{
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin: 0.6rem 0 0.2rem;
}}
.ag-plan-block {{
    background: #ffffff;
    border: 1px solid #e4e9ef;
    border-left: 3px solid #1F6B45;
    border-radius: 6px;
    padding: 0.7rem 0.9rem 0.75rem;
}}
.ag-plan-block-title {{
    font-size: 0.9rem;
    font-weight: 700;
    color: #1f5f3a;
    margin-bottom: 0.35rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px dashed #e2efe7;
}}
.ag-plan-block ul {{
    margin: 0;
    padding-left: 1.15rem;
}}
.ag-plan-block li {{
    font-size: 0.85rem;
    line-height: 1.85;
    color: #37474f;
    margin-bottom: 0.15rem;
}}
.ag-plan-block li strong {{
    color: #0d5c63;
    font-weight: 700;
}}
.ag-plan-empty {{
    padding: 1rem;
    text-align: center;
    color: #b0bec5;
    font-size: 0.82rem;
}}

/* -------- 地块卡片内的紧凑信息格（替代 st.metric） --------
 * 为什么不用 st.metric：Streamlit 的 metric 数值字号约 2rem，
 * 在四列布局里"诊断次数 6"会显得过分巨大，而日期类长文本会被截断成
 * 「2026年5...」（用户实际反馈"字太大了、不好看"）。
 * 这里改自绘信息格：数值字号可控、长文本自动换行不截断、标签在上值在下。
 */
.ag-plot-stats {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
    margin: 0.15rem 0 0.6rem;
}}
.ag-plot-stat {{
    background: #f8fafc;
    border: 1px solid #e8eef3;
    border-radius: 4px;
    padding: 0.5rem 0.65rem;
}}
.ag-plot-stat-lbl {{
    font-size: 0.7rem;
    color: #90a4ae;
    font-weight: 600;
    letter-spacing: 0.02em;
    margin-bottom: 0.18rem;
}}
.ag-plot-stat-val {{
    font-size: 0.92rem;
    font-weight: 700;
    color: #2c3e50;
    line-height: 1.35;
    word-break: break-word;
}}
.ag-plot-stat-val.accent {{ color: #1F6B45; }}
@media only screen and (max-width: 768px) {{
    .ag-plot-stats {{ grid-template-columns: repeat(2, 1fr); gap: 0.4rem; }}
    .ag-plot-stat-val {{ font-size: 0.88rem; }}
}}

/* -------- 识别结果卡（模块1）-------- */
.ag-rpt-identify {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.55rem;
}}
.ag-rpt-id-field {{
    background: #f8fafc;
    border: 1px solid #eef2f6;
    border-radius: 4px;
    padding: 0.5rem 0.6rem;
}}
.ag-rpt-id-lbl {{
    font-size: 0.66rem;
    font-weight: 600;
    color: #90a4ae;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.15rem;
}}
.ag-rpt-id-val {{
    font-size: 0.86rem;
    font-weight: 600;
    color: #2c3e50;
    line-height: 1.3;
}}
.ag-rpt-id-val.err {{ color: {t.danger}; }}
.ag-rpt-id-val.warn {{ color: {t.warning}; }}
.ag-rpt-id-val.ok {{ color: {t.brand}; }}
.ag-rpt-id-val.note {{ color: #90a4ae; font-weight: 500; }}
.ag-rpt-id-full {{
    grid-column: 1 / -1;
}}

.ag-rpt-risk {{
    background: #fff7f0;
    border: 1px solid #f0c9a6;
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-top: 0.7rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.8rem;
}}
.ag-rpt-risk.none {{
    background: #f2f8f4;
    border-color: #a8cdb6;
}}
.ag-rpt-risk.high {{
    background: #fdf3f2;
    border-color: #e3a8a4;
}}
.ag-rpt-risk-txt {{
    font-size: 0.85rem;
    font-weight: 700;
    color: #2c3e50;
}}
.ag-rpt-risk-desc {{
    font-size: 0.72rem;
    color: #78909c;
    margin-top: 0.15rem;
}}

/* -------- 智能体依据卡（模块2）-------- */
.ag-rpt-evidence {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.55rem;
}}
.ag-rpt-ev-card {{
    border: 1px solid #eef2f6;
    border-radius: 4px;
    padding: 0.55rem 0.7rem;
    background: #fafcfe;
}}
.ag-rpt-ev-card.success {{ border-left: 3px solid {t.brand}; background: #f6faf7; }}
.ag-rpt-ev-card.skip {{ border-left: 3px solid #cfd8dc; background: #f8fafc; opacity: 0.85; }}
.ag-rpt-ev-card.fail {{ border-left: 3px solid {t.danger}; background: #fdecea; }}
.ag-rpt-ev-head {{
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin-bottom: 0.3rem;
}}
.ag-rpt-ev-icon {{
    width: 1.4rem;
    height: 1.4rem;
    border-radius: 5px;
    background: #e8f5e9;
    color: {t.brand};
    font-size: 0.78rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
}}
.ag-rpt-ev-title {{
    font-size: 0.8rem;
    font-weight: 700;
    color: #2c3e50;
    flex: 1;
    min-width: 0;
}}
.ag-rpt-ev-badge {{
    font-size: 0.62rem;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 4px;
    background: #e8f5e9;
    color: {t.brand};
}}
.ag-rpt-ev-badge.skip {{ background: #e0e0e0; color: #757575; }}
.ag-rpt-ev-badge.fail {{ background: #ffebee; color: {t.danger}; }}
.ag-rpt-ev-body {{
    font-size: 0.74rem;
    color: #546e7a;
    line-height: 1.55;
}}
.ag-rpt-ev-stat {{
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    color: #78909c;
    margin-top: 0.2rem;
}}

/* -------- 植保建议（模块3）-------- */
.ag-rpt-advice {{
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
}}
.ag-rpt-advice-block {{
    border-left: 3px solid {t.brand};
    padding: 0.3rem 0 0.3rem 0.7rem;
}}
.ag-rpt-advice-title {{
    font-size: 0.84rem;
    font-weight: 700;
    color: #2c3e50;
    margin-bottom: 0.25rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}
.ag-rpt-advice-title .bullet {{
    width: 6px; height: 6px;
    border-radius: 50%;
    background: {t.brand};
    flex-shrink: 0;
}}
.ag-rpt-advice-body {{
    font-size: 0.8rem;
    color: #546e7a;
    line-height: 1.65;
}}
.ag-rpt-advice-body ul {{ margin: 0; padding-left: 1.1rem; }}
.ag-rpt-advice-body li {{ margin-bottom: 0.15rem; }}

/* -------- 农户端精简建议（要点式，宽松行距 + 重点加粗）-------- */
.ag-rpt-brief {{
    margin: 0.1rem 0 0.15rem;
    padding-left: 1.15rem;
}}
.ag-rpt-brief li {{
    line-height: 1.95;
    margin-bottom: 0.42rem;
    color: #37474f;
    font-size: 0.86rem;
}}
.ag-rpt-brief li:last-child {{ margin-bottom: 0.1rem; }}
.ag-rpt-brief li strong {{
    color: #1b5e20;
    font-weight: 700;
}}

.ag-rpt-risk-block {{
    border-left-color: {t.warning};
}}
.ag-rpt-risk-block .bullet {{ background: {t.warning}; }}

.ag-rpt-current {{
    border-left-color: #0d5c63;
}}
.ag-rpt-current .bullet {{ background: #0d5c63; }}

.ag-rpt-farm {{
    border-left-color: #6d4c41;
}}
.ag-rpt-farm .bullet {{ background: #6d4c41; }}

/* -------- 可信 AI 说明（模块4）-------- */
.ag-rpt-trust {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 0.5rem;
}}
.ag-rpt-trust-card {{
    background: #f8fafc;
    border: 1px solid #eef2f6;
    border-radius: 4px;
    padding: 0.6rem 0.7rem;
    text-align: center;
}}
.ag-rpt-trust-icon {{
    font-size: 1.4rem;
    line-height: 1;
    margin-bottom: 0.3rem;
}}
.ag-rpt-trust-title {{
    font-size: 0.78rem;
    font-weight: 700;
    color: #2c3e50;
    margin-bottom: 0.15rem;
}}
.ag-rpt-trust-desc {{
    font-size: 0.68rem;
    color: #90a4ae;
    line-height: 1.45;
}}

.ag-rpt-disclaimer {{
    background: #fefefe;
    border: 1px dashed #cfd8dc;
    border-radius: 4px;
    padding: 0.7rem 0.85rem;
    margin-top: 0.7rem;
    font-size: 0.72rem;
    color: #78909c;
    line-height: 1.7;
}}

.ag-rpt-source {{
    text-align: center;
    font-size: 0.65rem;
    color: #b0bec5;
    margin-top: 0.5rem;
}}

/* -------- 结果页 操作按钮 -------- */
.ag-rpt-actions {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    margin-top: 0.8rem;
}}
.ag-rpt-actions .stDownloadButton button,
.ag-rpt-actions .stButton button {{
    height: 2.6rem;
    font-size: 0.82rem;
    font-weight: 600;
    border-radius: 4px;
}}

/* ==========================================================
 * 农智链 AgriAgent — 农技员管理驾驶舱（比赛截图专用）
 * ========================================================== */
.ag-adm-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.55rem;
    margin: 0.4rem 0 0.7rem;
}}

/* -------- 指标说明条（消除"只能管这些"的误解）-------- */
.ag-adm-note {{
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
    background: #f8fafc;
    border: 1px solid #e4e9ef;
    border-left: 3px solid #90a4ae;
    border-radius: 4px;
    padding: 0.5rem 0.7rem;
    margin: 0.35rem 0 0.6rem;
    font-size: 0.76rem;
    line-height: 1.65;
    color: #607d8b;
}}
.ag-adm-note b {{ color: #37474f; font-weight: 700; }}
.ag-adm-note-tag {{
    flex: 0 0 auto;
    font-size: 0.66rem;
    font-weight: 700;
    color: #fff;
    background: #90a4ae;
    border-radius: 3px;
    padding: 0.1rem 0.35rem;
    margin-top: 0.1rem;
    letter-spacing: 0.03em;
}}

/* -------- 农户端症状常用词（列内换行，禁止横向滚动）-------- */
/* st.pills 默认可能给每个 pill 设最小宽度，中文标签在窄列里会溢出成横向滚动。
   这里强制允许收缩与换行。 */
[data-testid="stPills"] {{
    max-width: 100%;
    overflow-x: hidden;
}}
[data-testid="stPills"] ul,
[data-testid="stPills"] > div {{
    flex-wrap: wrap !important;
    row-gap: 0.3rem;
    max-width: 100%;
}}
[data-testid="stPills"] li,
[data-testid="stPills"] button {{
    min-width: 0 !important;
    max-width: 100%;
    white-space: nowrap;
}}

/* -------- 等高统计卡一行（替代多个 st.columns，避免卡片高度不齐）--------
 * 问题：把统计卡分别放进独立的 st.columns 时，每列高度由各自内容决定，
 * 内容多的那一列（例如列出几十个名称、换成 3 行）会把卡片撑高，
 * 同一行里就出现高低不齐（用户实际反馈）。
 * 解法：把整行卡片放进同一个 flex 容器，用 align-items: stretch
 * 让所有卡片拉伸到该行最高者，天然等高。
 */
.ag-cards {{
    display: flex;
    gap: 0.75rem;
    align-items: stretch;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
}}
.ag-cards > .ag-card {{
    flex: 1 1 0;
    min-width: 12rem;
    margin-bottom: 0 !important;
    display: flex;
    flex-direction: column;
}}
/* 值与其下的说明都靠上，卡片被拉伸后底部留白均匀，不会出现孤立空白 */
.ag-cards > .ag-card .ag-card-value {{
    margin-bottom: 0.2rem;
}}
.ag-cards > .ag-card .ag-card-trend {{
    flex: 1 1 auto;
}}

/* -------- 农户端图片输入：拍照按钮风格与上传框对齐 --------
 * 注意（重要教训）：不要约束 stCameraInput 内部 video/canvas 的尺寸，
 * 也不要给其容器加 overflow:hidden / padding:0 ——
 * 实测会导致画面容器塌陷、只显示一个相机图标、无法取景。
 * 这里只调整"拍照"按钮自身的外观，其余保持 Streamlit 原生渲染。
 * 选择器取自 Streamlit 前端实现（CameraInput.B3VD66Ch.js）：
 *   stCameraInputButton / stCameraInputSwitchButton
 */
[data-testid="stCameraInputButton"] {{
    border-radius: 6px !important;
    font-size: 0.86rem !important;
    font-weight: 500 !important;
    padding: 0.4rem 0.8rem !important;
}}
/* 切换前后摄像头按钮：小尺寸，不抢视线 */
[data-testid="stCameraInputSwitchButton"] button {{
    min-height: 1.6rem !important;
    padding: 0.1rem 0.3rem !important;
}}

/* -------- 横向条形图（自绘，替代 st.bar_chart 避免中文标签竖排）-------- */
.ag-chart {{
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 0.2rem 0 0.1rem;
}}
.ag-chart-row {{
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-size: 0.8rem;
    line-height: 1.4;
}}
.ag-chart-lbl {{
    flex: 0 0 auto;
    width: 6.6rem;
    text-align: right;
    color: #37474f;
    font-weight: 600;
    font-size: 0.78rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.ag-chart-track {{
    flex: 1 1 auto;
    min-width: 3rem;
    height: 16px;
    background: #f1f5f9;
    border-radius: 4px;
    overflow: hidden;
}}
.ag-chart-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width .25s ease;
}}
.ag-chart-val {{
    flex: 0 0 auto;
    min-width: 2.6rem;
    text-align: right;
    font-weight: 700;
    color: #2c3e50;
    font-size: 0.8rem;
}}
.ag-chart-pct {{
    flex: 0 0 auto;
    min-width: 2.9rem;
    text-align: right;
    color: #90a4ae;
    font-size: 0.7rem;
}}
.ag-chart-empty {{
    padding: 1.2rem 0;
    text-align: center;
    color: #b0bec5;
    font-size: 0.8rem;
}}

/* -------- 紧凑指标行（替代一列 st.metric）-------- */
.ag-mini-stats {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.45rem;
    margin-top: 0.4rem;
}}
.ag-mini-stat {{
    background: #f8fafc;
    border: 1px solid #eef2f6;
    border-left: 3px solid #90a4ae;
    border-radius: 4px;
    padding: 0.45rem 0.6rem;
}}
.ag-mini-stat-lbl {{
    font-size: 0.7rem;
    color: #78909c;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.ag-mini-stat-val {{
    font-size: 1.05rem;
    font-weight: 800;
    color: #2c3e50;
    line-height: 1.2;
    margin-top: 0.1rem;
}}
.ag-mini-stat-val sub {{
    font-size: 0.66rem;
    font-weight: 500;
    color: #90a4ae;
    margin-left: 2px;
}}
.ag-mini-stat-hint {{
    font-size: 0.64rem;
    color: #b0bec5;
    margin-top: 0.08rem;
}}
@media only screen and (max-width: 768px) {{
    .ag-chart-lbl {{ width: 4.6rem; font-size: 0.72rem; }}
    .ag-chart-track {{ height: 14px; }}
    .ag-mini-stats {{ grid-template-columns: repeat(2, 1fr); gap: 0.35rem; }}
}}

/* -------- 系统能力区（与业务数据明确区分）-------- */
.ag-adm-capab {{
    background: #f4f9f6;
    border: 1px solid #dcebe1;
    border-left: 3px solid #1F6B45;
    border-radius: 6px;
    padding: 0.8rem 0.9rem 0.85rem;
    margin: 0.3rem 0 0.2rem;
}}
.ag-adm-capab-title {{
    font-size: 0.86rem;
    font-weight: 700;
    color: #1f5f3a;
    margin-bottom: 0.15rem;
}}
.ag-adm-capab-sub {{
    font-size: 0.7rem;
    color: #78909c;
    margin-bottom: 0.6rem;
}}
.ag-adm-capab-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 0.5rem;
}}
.ag-adm-capab-item {{
    background: #ffffff;
    border: 1px solid #e2efe7;
    border-radius: 4px;
    padding: 0.55rem 0.7rem;
}}
.ag-adm-capab-num {{
    font-size: 1.15rem;
    font-weight: 800;
    color: #1F6B45;
    line-height: 1.15;
}}
.ag-adm-capab-num sub {{
    font-size: 0.68rem;
    font-weight: 500;
    color: #90a4ae;
    margin-left: 2px;
}}
.ag-adm-capab-lbl {{
    font-size: 0.74rem;
    font-weight: 600;
    color: #37474f;
    margin-top: 0.15rem;
}}
.ag-adm-capab-hint {{
    font-size: 0.66rem;
    color: #90a4ae;
    margin-top: 0.12rem;
    line-height: 1.5;
}}
.ag-adm-kpi {{
    background: #ffffff;
    border: 1px solid #e4e9ef;
    border-radius: 4px;
    padding: 0.85rem 0.9rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}}
.ag-adm-kpi::before {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    background: var(--kpi-accent, {t.brand});
}}
.ag-adm-kpi-num {{
    font-size: 1.65rem;
    font-weight: 800;
    color: #2c3e50;
    line-height: 1.1;
    letter-spacing: -0.01em;
}}
.ag-adm-kpi-num sub {{
    font-size: 0.7rem;
    font-weight: 500;
    color: #90a4ae;
    margin-left: 2px;
}}
.ag-adm-kpi-lbl {{
    font-size: 0.76rem;
    color: #78909c;
    font-weight: 500;
    margin-top: 0.2rem;
}}
.ag-adm-kpi-hint {{
    font-size: 0.66rem;
    color: #b0bec5;
    margin-top: 0.15rem;
}}

.ag-adm-bar-row {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.35rem;
    font-size: 0.76rem;
}}
.ag-adm-bar-label {{
    width: 44px;
    font-weight: 600;
    flex-shrink: 0;
}}
.ag-adm-bar-track {{
    flex: 1;
    height: 7px;
    background: #f1f5f9;
    border-radius: 4px;
    overflow: hidden;
}}
.ag-adm-bar-fill {{
    height: 100%;
    border-radius: 4px;
}}
.ag-adm-bar-val {{
    width: 26px;
    text-align: right;
    font-weight: 700;
    color: #2c3e50;
}}
.ag-adm-bar-pct {{
    width: 42px;
    text-align: right;
    color: #90a4ae;
    font-size: 0.68rem;
}}

.ag-adm-tbl {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.76rem;
}}
.ag-adm-tbl thead th {{
    background: #f8fafc;
    font-size: 0.7rem;
    font-weight: 600;
    color: #78909c;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.4rem 0.55rem;
    border-bottom: 1px solid #e4e9ef;
    text-align: left;
}}
.ag-adm-tbl tbody td {{
    padding: 0.45rem 0.55rem;
    border-bottom: 1px solid #f1f5f9;
    color: #37474f;
}}
.ag-adm-tbl tbody tr:hover td {{
    background: #fafbfc;
}}
.ag-adm-tbl .risk-high td:first-child {{ border-left: 3px solid {t.danger}; }}
.ag-adm-tbl .risk-mid td:first-child {{ border-left: 3px solid {t.warning}; }}
.ag-adm-tbl .risk-low td:first-child {{ border-left: 3px solid #1976d2; }}

.ag-adm-summary {{
    background: #ffffff;
    border: 1px solid #e4e9ef;
    border-left: 3px solid {t.brand};
    border-radius: 6px;
    padding: 0.85rem 1rem;
    color: #546e7a;
    margin-top: 0.3rem;
}}
.ag-adm-summary-title {{
    font-size: 0.78rem;
    font-weight: 700;
    color: {t.neutral};
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}
.ag-adm-summary-body {{
    font-size: 0.82rem;
    line-height: 1.65;
}}
.ag-adm-summary-body b {{
    color: {t.brand};
    font-weight: 700;
}}

.ag-adm-kpi-grid-mobile {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.45rem;
}}

/* -------- 状态/风险徽章（admin_tasks.py 使用）-------- */
.badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.01em;
}}
.badge-high {{
    background: #fdecea;
    color: #c0392b;
    border: 1px solid #f5b7b1;
}}
.badge-mid {{
    background: #fff5e6;
    color: #d68910;
    border: 1px solid #f9e79f;
}}
.badge-low {{
    background: #eaf2ff;
    color: #1976d2;
    border: 1px solid #aed6f1;
}}

/* ==========================================================
 * 手机端专属样式（比赛演示用）
 * ========================================================== */

/* -------- Hero 头部 -------- */
.ag-m-hero {{
    background: #ffffff;
    border: 1px solid {t.neutral_5};
    border-left: 4px solid {t.brand};
    border-radius: 4px;
    padding: 1rem 1.05rem;
    margin: 0.25rem 0 0.6rem;
    color: {t.neutral};
}}
.ag-m-hero-badge {{
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 500;
    background: #e8f1ec;
    color: {t.brand};
    padding: 2px 10px;
    border-radius: 3px;
    letter-spacing: 0.02em;
}}
.ag-m-hero-title {{
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    margin: 0.25rem 0 0.05rem;
    line-height: 1.2;
    color: {t.neutral};
}}
.ag-m-hero-sub {{
    font-size: 0.78rem;
    color: {t.neutral_3};
    margin-bottom: 0.65rem;
    line-height: 1.5;
}}

/* -------- 等待提示 -------- */
.ag-m-wait {{
    text-align: center;
    padding: 2rem 1rem;
    color: #90a4ae;
}}

/* -------- 我的地块（紧凑卡片）-------- */
.ag-m-plot {{
    background: #fff;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #1f5f3a;
    border-radius: 4px;
    padding: 0.65rem 0.85rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}}

/* -------- 结果头卡 -------- */
.ag-m-result-head {{
    background: {t.brand};
    border-radius: 6px;
    padding: 1rem 1.1rem;
    margin: 0.4rem 0 0.8rem;
    color: #fff;
}}
.ag-m-result-disease {{
    font-size: 1.2rem;
    font-weight: 800;
    line-height: 1.25;
}}
.ag-m-chip {{
    display: inline-block;
    padding: 2px 10px;
    background: #e8f1ec;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 500;
    color: #fff;
}}

/* -------- 知识依据紧凑卡 -------- */
.ag-m-kref {{
    background: #fff;
    border-radius: 6px;
    padding: 0.55rem 0.7rem;
    font-size: 0.82rem;
    line-height: 1.7;
}}

/* -------- 智能体时间线 -------- */
.ag-m-timeline {{
    position: relative;
    padding-left: 1.2rem;
    margin-top: 0.3rem;
}}
.ag-m-timeline::before {{
    content: '';
    position: absolute;
    left: 0.38rem;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #e2e8f0;
}}
.ag-m-tl-item {{
    display: flex;
    gap: 0.6rem;
    padding: 0.35rem 0;
    position: relative;
}}
.ag-m-tl-dot {{
    flex-shrink: 0;
    width: 1.2rem;
    height: 1.2rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.65rem;
    font-weight: 700;
    background: #f1f5f9;
    color: #b0bec5;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1px #e2e8f0;
    position: relative;
    z-index: 1;
}}
.ag-m-tl-body {{
    flex: 1;
    min-width: 0;
}}
.ag-m-step-done .ag-m-tl-dot  {{ background: #1f5f3a; color: #fff; box-shadow: 0 0 0 1px #1f5f3a; }}
.ag-m-step-run .ag-m-tl-dot   {{ background: #0288d1; color: #fff; box-shadow: 0 0 0 1px #0288d1;  }}
.ag-m-step-fail .ag-m-tl-dot  {{ background: #c0392b; color: #fff; box-shadow: 0 0 0 1px #c0392b; }}
.ag-m-step-skip .ag-m-tl-dot  {{ background: #e2e8f0; color: #90a4ae; }}
.ag-m-step-pend .ag-m-tl-dot {{ background: #f1f5f9; color: #b0bec5; }}  

/* ==========================================================
 * 响应式：手机端（≤ 768px）— 完整覆盖 Streamlit 原生组件
 * ========================================================== */
@media only screen and (max-width: 768px) {{
    /* 容器：减小 padding，撑满宽度 */
    .block-container {{
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
    }}

    /* 隐藏 Streamlit 顶部 toolbar 占位 */
    .stApp header {{ display: none !important; }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    .block-container > div:first-child {{ padding-top: 0 !important; }}

    /* Sidebar 在手机端强制隐藏 */
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="collapsedControl"] {{ display: none !important; }}

    /* 标题字号逐级缩小 */
    h1, h2 {{ font-size: 1.1rem !important; font-weight: 700 !important; }}
    h3 {{ font-size: 0.98rem !important; font-weight: 700 !important; }}
    h4 {{ font-size: 0.88rem !important; font-weight: 600 !important; }}
    h5, h6 {{ font-size: 0.82rem !important; font-weight: 600 !important; }}

    /* 所有按钮 100% 宽度 */
    .stButton, .stDownloadButton {{ width: 100% !important; margin-bottom: 0.35rem; }}
    .stButton button, .stDownloadButton button {{
        width: 100% !important;
        font-size: 0.9rem !important;
        padding: 0.55rem 1rem !important;
        border-radius: 6px !important;
    }}

    /* 文件上传 */
    [data-testid="stFileUploader"] {{ width: 100% !important; }}
    [data-testid="stFileUploader"] section {{ width: 100% !important; }}
    [data-testid="stFileUploader"] button {{ width: 100% !important; }}

    /* Selectbox / TextInput / TextArea */
    .stSelectbox, .stTextInput, .stTextArea, .stNumberInput, .stDateInput, .stTimeInput {{
        width: 100% !important;
        margin-bottom: 0.35rem;
    }}
    .stSelectbox > div > div > div,
    .stTextInput > div > div > div,
    .stTextArea > div > div > div {{
        font-size: 0.88rem !important;
    }}

    /* Radio 按钮组竖排 */
    .stRadio [role="radiogroup"] {{
        flex-direction: column !important;
        gap: 0.25rem !important;
    }}
    .stRadio label {{ font-size: 0.85rem !important; }}

    /* Checkbox */
    .stCheckbox label {{ font-size: 0.85rem !important; }}

    /* label 字号统一 */
    label {{ font-size: 0.8rem !important; margin-bottom: 0.15rem !important; }}

    /* expander 内边距 */
    [data-testid="stExpander"] {{ padding: 0.25rem 0 !important; }}
    [data-testid="stExpander"] summary {{ padding: 0.35rem 0.5rem !important; font-size: 0.88rem !important; }}

    /* divider 更紧凑 */
    hr {{ margin: 0.6rem 0 !important; }}

    /* 状态胶囊 */
    [data-testid="stStatusWidget"] {{ padding: 0.3rem 0.4rem !important; font-size: 0.82rem !important; }}

    /* 卡片紧凑 */
    .ag-card {{ padding: 0.55rem 0.7rem !important; margin-bottom: 0.4rem !important; }}
    .ag-stat-card {{ padding: 0.5rem 0.65rem !important; }}
    .ag-tools-grid {{ grid-template-columns: 1fr; gap: 0.45rem; }}
    .ag-tool-card {{ padding: 0.6rem 0.7rem !important; }}

    /* Agent 工作流移动端 */
    .ag-flow {{ padding: 0.65rem 0.6rem 0.45rem; margin-bottom: 0.6rem; }}
    .ag-flow-title {{ font-size: 0.84rem; }}
    .ag-flow-step {{ padding: 0.5rem 0.6rem; border-left-width: 2px; }}
    .ag-flow-icon {{ width: 1.6rem; height: 1.6rem; font-size: 0.8rem; border-radius: 6px; }}
    .ag-flow-name-main {{ font-size: 0.78rem; }}
    .ag-flow-name-sub {{ font-size: 0.64rem; }}
    .ag-flow-body {{ grid-template-columns: 1fr; gap: 0.28rem; }}
    .ag-flow-status {{ font-size: 0.64rem; padding: 1px 6px; }}
    .ag-flow-io {{ font-size: 0.7rem; padding: 0.3rem 0.4rem; }}
    .ag-flow-io-lbl {{ font-size: 0.58rem; }}
    .ag-flow-io-val {{ font-size: 0.72rem; }}
    .ag-flow-final {{ padding: 0.55rem 0.65rem; flex-direction: column; align-items: flex-start; gap: 0.25rem; }}
    .ag-flow-final-txt {{ font-size: 0.8rem; }}

    /* AI 诊断报告移动端 */
    .ag-rpt-header {{
    background: #ffffff;
    border: 1px solid {t.neutral_5};
    border-left: 4px solid {t.brand};
    border-radius: 4px;
    padding: 0.9rem 1.1rem;
    margin: 0.3rem 0 0.7rem;
    color: {t.neutral};
}}
    .ag-rpt-hd-title {{
    font-size: 1.35rem;
    font-weight: 700;
    margin: 0.35rem 0 0.1rem;
    letter-spacing: 0.01em;
    color: {t.neutral};
}}
    .ag-rpt-hd-sub {{
    font-size: 0.78rem;
    color: {t.neutral_3};
    line-height: 1.5;
    margin-bottom: 0.5rem;
}}
    .ag-rpt-section {{ padding: 0.7rem 0.75rem; margin: 0.4rem 0; }}
    .ag-rpt-sec-title {{ font-size: 0.84rem; }}
    .ag-rpt-identify {{ grid-template-columns: 1fr; gap: 0.4rem; }}
    .ag-rpt-evidence {{ grid-template-columns: 1fr; gap: 0.4rem; }}
    .ag-rpt-trust {{ grid-template-columns: 1fr 1fr; gap: 0.4rem; }}
    .ag-rpt-trust-card {{ padding: 0.5rem; }}
    .ag-rpt-risk {{ padding: 0.6rem 0.7rem; }}
    .ag-rpt-actions {{ grid-template-columns: 1fr 1fr; gap: 0.4rem; }}
    .ag-rpt-actions .stDownloadButton button,
    .ag-rpt-actions .stButton button {{ height: 2.4rem; font-size: 0.78rem; }}
    .ag-score-num {{ font-size: 2.2rem; }}

    .ag-risk-high, .ag-risk-mid, .ag-risk-low, .ag-risk-none {{
        font-size: 0.72rem; padding: 1px 6px;
    }}
    .ag-status-done, .ag-status-running, .ag-status-failed {{ font-size: 0.7rem; }}

    /* Hero / 结果头卡移动端 */
    .ag-m-hero {{
    background: #ffffff;
    border: 1px solid {t.neutral_5};
    border-left: 4px solid {t.brand};
    border-radius: 4px;
    padding: 1rem 1.05rem;
    margin: 0.25rem 0 0.6rem;
    color: {t.neutral};
}}
    .ag-m-hero-title {{ font-size: 1.25rem; }}
    .ag-m-result-head {{ padding: 0.75rem; }}
    .ag-m-result-disease {{ font-size: 1rem; }}

    /* Streamlit image */
    [data-testid="stImage"] img {{ max-width: 100%; height: auto; border-radius: 6px; }}
}}

@media only screen and (max-width: 480px) {{
    .ag-m-hero-title {{ font-size: 1.1rem; }}
    .ag-m-hero-sub   {{ font-size: 0.72rem; }}
    .ag-m-result-disease {{ font-size: 0.95rem; }}
}}
</style>
"""


def inject_theme() -> None:
    """一次性注入全局主题 CSS（在 app.py 顶部调用）。"""
    import streamlit as st
    st.markdown(build_css(DEFAULT_THEME), unsafe_allow_html=True)


__all__ = ["Theme", "DEFAULT_THEME", "build_css", "inject_theme"]
