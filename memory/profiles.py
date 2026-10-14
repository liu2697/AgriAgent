"""地块档案扩展存储：地块基础信息（土壤/经纬度/播种时间）与农事日志。

数据已迁移至 SQLite（data/agragent.db）：
- 地块基础档案字段并入 plots 表（与地块 1:1，无独立建表必要）
- 农事日志拆分至独立 farming_logs 表
- 原 plot_profiles.json 保留为迁移备份，运行时不再读写。

对外函数接口与 JSON 版本完全兼容，调用方无需修改。
"""
from __future__ import annotations

from database import repository as repo
from memory.history import MEMORY_DIR  # noqa: F401  兼容保留（旧路径引用）

# 兼容保留：旧 JSON 文件路径（迁移备份用，运行时不再读写）
PROFILE_FILE = MEMORY_DIR / "plot_profiles.json"

# 支持的农事日志类型
LOG_TYPES = ("灌溉", "施肥", "打药", "巡田")


def get_profile(plot_key: str) -> dict:
    """获取地块基础信息（无档案时返回空 dict）。"""
    row = repo.get_plot(plot_key)
    if not row:
        return {}
    return {
        "soil_type": row.get("soil_type", ""),
        "latitude": row.get("latitude", ""),
        "longitude": row.get("longitude", ""),
        "planting_date": row.get("planting_date", ""),
        "updated_at": row.get("updated_at", ""),
    }


def save_profile(plot_key: str, soil_type: str = "", latitude: str = "",
                 longitude: str = "", planting_date: str = "") -> dict:
    """保存/更新地块基础信息（土壤、经纬度、播种时间）。

    地块行不存在时自动创建（此时 location/crop 未知，留空）。
    """
    repo.upsert_plot(
        plot_key,
        soil_type=soil_type,
        latitude=latitude,
        longitude=longitude,
        planting_date=planting_date,
    )
    return get_profile(plot_key)


def add_log(plot_key: str, log_type: str, note: str) -> dict:
    """追加一条农事日志（灌溉/施肥/打药/巡田）。"""
    if log_type not in LOG_TYPES:
        raise ValueError(f"不支持的日志类型：{log_type}")
    return repo.create_farming_log(plot_key, log_type, note)


def get_logs(plot_key: str) -> list[dict]:
    """获取地块全部农事日志（按时间正序）。"""
    return repo.list_farming_logs(plot_key)


def delete_profile(plot_key: str) -> bool:
    """删除地块扩展档案（随地块删除联动调用）。

    注意：档案字段并入 plots 表，此处删除 plots 行即删除档案；
    诊断记录与工单不受影响（与原 JSON 行为一致）。
    """
    return repo.delete_plot(plot_key)


__all__ = [
    "LOG_TYPES",
    "get_profile",
    "save_profile",
    "add_log",
    "get_logs",
    "delete_profile",
]
