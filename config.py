import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "农智链 AgriAgent"
APP_SUBTITLE = "北方大田智能植保与生产管理智能体平台"
APP_ICON = "🌾"
APP_VERSION = "1.1.0"

# 北方大田作物（华北、东北、内蒙古及西北旱作区主要种植作物）
#
# 覆盖范围：粮食作物 + 油料作物 + 经济作物 + 杂粮豆类 + 饲草，共 24 种，
# 末尾「其他」用于农户种植本列表未收录作物时手工填写。
# 新增作物时需三处同步：
#   1. 本列表
#   2. knowledge_center/crop_aliases.py（别名表，决定"农户写俗称也能识别"）
#   3. knowledge_center/loader.py 的 _crop_to_filename 与
#      tools/build_crop_data.py 的 _FILENAMES（数据文件映射）
CROPS = [
    # 主要粮食作物
    "玉米",
    "小麦",
    "水稻",
    "马铃薯",
    # 杂粮（北方旱作区主栽）
    "谷子",
    "糜子",
    "燕麦",
    "荞麦",
    "大麦",
    "高粱",
    # 豆类
    "大豆",
    "绿豆",
    "豌豆",
    "蚕豆",
    "红小豆",
    # 油料作物
    "花生",
    "油菜",
    "向日葵",
    "芝麻",
    "亚麻",
    "蓖麻",
    # 经济作物
    "棉花",
    "甜菜",
    # 饲草
    "苜蓿",
    # 兜底：农户种植列表中未收录的作物时手工填写
    "其他",
]

SOIL_TYPES = [
    "壤土",
    "沙土",
    "粘土",
    "黑土",
    "红壤",
    "黄壤",
    "盐碱土",
    "其他",
]

GROWTH_STAGES = [
    "播种期",
    "发芽期",
    "幼苗期",
    "生长期",
    "开花期",
    "结果期",
    "成熟期",
]

# 配置读取诊断（供日志与农技员端"环境自检"面板使用；**不记录任何密钥明文**）
CONFIG_WARNINGS: list[str] = []
_CONFIG_SOURCE: dict[str, str] = {}


def _get_env(name: str, default: str = "") -> str:
    """读取配置：环境变量（.env）优先，未设置时回退到 Streamlit Secrets。

    Streamlit Community Cloud 等云平台通过 Secrets 注入配置
    （AI_API_KEY / AI_MODEL / ADMIN_PASSWORD 等），本地开发仍用 .env。

    与早期版本的区别：Secrets 读取异常（文件缺失、TOML 语法错误等）**不再被静默丢弃**，
    而是记录到 CONFIG_WARNINGS 并写入服务器日志，便于在
    "Manage app → Logs" 与农技员端"环境自检"面板中直接看到原因。
    """
    val = os.getenv(name)
    if val:
        _CONFIG_SOURCE[name] = "环境变量(.env)"
        return val
    try:
        import streamlit as st  # 延迟导入：测试等非 Streamlit 环境不依赖
        secret = st.secrets.get(name)
        if secret is not None and str(secret).strip() != "":
            _CONFIG_SOURCE[name] = "云端 Secrets"
            return str(secret).strip()
        _CONFIG_SOURCE[name] = "未配置"
    except Exception as exc:  # noqa: BLE001 — 记录原因，不再静默
        _CONFIG_SOURCE[name] = "读取失败"
        msg = f"读取 Streamlit Secrets 失败：{type(exc).__name__}: {exc}"
        if msg not in CONFIG_WARNINGS:
            CONFIG_WARNINGS.append(msg)
    return default


# AI 模型配置
# 视觉诊断要求模型支持图片输入（多模态）。若使用纯文本模型（deepseek-chat /
# qwen-plus 等），上传的图片不会参与诊断，ai_service 会自动降级为纯文字模式。
#
# 已实测（2026-01，本机 Key · DashScope OpenAI 兼容接口）：
#   qwen3-vl-plus     可用 · 支持图片  ← 默认推荐
#   qwen-plus         可用 · 纯文本
#   qwen-vl-plus      404 Model not exist（旧模型名已下线，勿使用）
#   qwen-vl-max       403 Access denied（当前 Key 无该模型权限）
# 注意：API Key 缺失时 ai_service 会返回「示例诊断」占位内容，不要误当成真实结论。
AI_API_KEY = _get_env("AI_API_KEY", "")
AI_API_URL = _get_env(
    "AI_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
)
AI_MODEL = _get_env("AI_MODEL", "qwen3-vl-plus")

# 是否为多模态（支持图片输入）模型：决定上传图片是否真正参与诊断
AI_MODEL_SUPPORTS_VISION = _get_env("AI_MODEL_SUPPORTS_VISION", "1") not in ("0", "false", "False")

# 农技员管理端登录密码（默认 admin123，可在 .env 或 Streamlit Secrets 中通过 ADMIN_PASSWORD 修改）
ADMIN_PASSWORD = _get_env("ADMIN_PASSWORD", "admin123")


def config_diagnostics() -> dict:
    """配置自检信息（供农技员端"环境自检"面板展示；不含密钥明文）。"""
    return {
        "api_key_set": bool(AI_API_KEY),
        "api_key_length": len(AI_API_KEY),
        "api_key_source": _CONFIG_SOURCE.get("AI_API_KEY", "默认值"),
        "api_url": AI_API_URL,
        "model": AI_MODEL,
        "vision": AI_MODEL_SUPPORTS_VISION,
        "admin_password_source": _CONFIG_SOURCE.get("ADMIN_PASSWORD", "默认值"),
        "warnings": list(CONFIG_WARNINGS),
    }


# 启动时把配置告警写入服务器日志：Streamlit Cloud 的「Manage app → Logs」可直接看到
if CONFIG_WARNINGS:
    import sys as _sys

    print("[config] 配置告警：" + "；".join(CONFIG_WARNINGS), file=_sys.stderr)
