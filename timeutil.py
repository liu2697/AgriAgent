# -*- coding: utf-8 -*-
"""统一时间工具：所有写入数据库与界面展示的时间一律使用北京时间（UTC+8）。

背景：Streamlit Community Cloud 等云容器默认使用 UTC 时区，
若直接使用 ``datetime.now()``，会把 UTC 时间当作本地时间写入数据库，
导致界面上的"提交时间 / 诊断时间 / 生成时间"比北京时间早 8 小时。
本模块返回 **naive 的北京时间**（数值即东八区墙上时间），
字符串格式与既有历史数据完全一致，避免影响排序与比较逻辑。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# 东八区（不使用 zoneinfo，避免依赖容器内 tzdata）
CN_TZ = timezone(timedelta(hours=8), "CST")


def now_cn() -> datetime:
    """当前北京时间（naive datetime，数值为东八区墙上时间）。"""
    return datetime.now(timezone.utc).astimezone(CN_TZ).replace(tzinfo=None)


def today_cn():
    """当前北京日期。"""
    return now_cn().date()


def iso_now() -> str:
    """当前北京时间的 ISO 字符串（秒级），与既有数据格式一致。"""
    return now_cn().isoformat(timespec="seconds")


__all__ = ["CN_TZ", "now_cn", "today_cn", "iso_now"]
