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
_ENV_FILE_VALUES: dict[str, str] = {}


def _env_file_values() -> dict[str, str]:
    """读取项目根目录 .env 的键值（仅用于判断"值的来源"；取不到时返回空字典）。"""
    global _ENV_FILE_VALUES
    if not _ENV_FILE_VALUES:
        try:
            from dotenv import dotenv_values

            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            if os.path.exists(path):
                _ENV_FILE_VALUES = {k: (v or "") for k, v in dotenv_values(path).items()}
        except Exception:  # noqa: BLE001 — 来源判定失败不影响取值
            _ENV_FILE_VALUES = {}
    return _ENV_FILE_VALUES


def _get_env(name: str, default: str = "") -> str:
    """读取配置：**云端 Secrets 优先**，其次环境变量（本地 .env / 平台注入），最后默认值。

    为什么 Secrets 优先（重要，踩过坑）：
        Streamlit Community Cloud 会把 Secrets **同时注入为容器环境变量**，而环境变量在
        容器启动那一刻就冻结了——**修改 Secrets 后，已运行容器的环境变量仍是旧值**。
        早期实现"环境变量优先"，就会出现"Secrets 里明明写着 admin123，登录却要 999999"
        这类灵异现象（旧环境变量把新 Secrets 盖住了）。改为 Secrets 优先后：
        改 Secrets → 应用重启即生效，不会再被陈旧环境变量覆盖。
        本地开发没有 secrets.toml（访问 st.secrets 会抛 SecretNotFound），
        会自动落到环境变量 / .env，行为不变。

    来源标注（供"环境自检"面板与日志排查）：
        - 云端 Secrets
        - 项目 .env 文件（仅本地存在）
        - 平台/系统环境变量

    另外：Secrets 读取异常（真 TOML 语法错误等）**不再被静默丢弃**，
    而是记录到 CONFIG_WARNINGS 并写入服务器日志（Manage app → Logs）。
    """
    # ---------- 1) 云端 Secrets（权威来源，优先级最高）----------
    try:
        import streamlit as st  # 延迟导入：测试等非 Streamlit 环境不依赖

        secret = st.secrets.get(name)
        if secret is not None and str(secret).strip() != "":
            _CONFIG_SOURCE[name] = "云端 Secrets"
            return str(secret).strip()
    except Exception as exc:  # noqa: BLE001 — 区分"未配置"与"真异常"
        exc_name = type(exc).__name__.lower()
        exc_msg = str(exc).lower()
        if not ("secretnotfound" in exc_name or "no secrets found" in exc_msg):
            # 真正的异常（如 Secrets 文件 TOML 语法错误）才告警；
            # "没有 secrets.toml"属正常情况（本地开发），不报错。
            # 告警后仍继续尝试环境变量兜底，避免因 Secrets 写错导致整站不可用。
            _CONFIG_SOURCE[name] = "读取失败"
            msg = f"读取 Streamlit Secrets 失败：{type(exc).__name__}: {exc}"
            if msg not in CONFIG_WARNINGS:
                CONFIG_WARNINGS.append(msg)

    # ---------- 2) 环境变量（本地 .env / 平台注入）----------
    val = os.getenv(name)
    if val:
        env_file = _env_file_values()
        if name in env_file and str(env_file.get(name, "")).strip() == str(val).strip():
            _CONFIG_SOURCE[name] = "项目 .env 文件"
        else:
            _CONFIG_SOURCE[name] = "平台/系统环境变量"
        return val

    # ---------- 3) 默认值 ----------
    _CONFIG_SOURCE.setdefault(name, "未配置")
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
