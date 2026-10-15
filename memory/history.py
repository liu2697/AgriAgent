"""地块历史与问题工单存储（SQLite 持久化）。

数据存储已从 JSON 文件迁移至 SQLite（data/agragent.db）：
- 诊断记录 → database.repository（diagnosis_records 表）
- 问题工单 → database.repository（tasks 表）
- 图片仍保存于文件系统 memory/store/task_images/，数据库仅存路径引用。

对外函数接口与 JSON 版本完全兼容，调用方无需修改。
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from database import repository as repo
from timeutil import iso_now, now_cn


MEMORY_DIR = Path(os.environ.get("AGENT_MEMORY_DIR", Path(__file__).resolve().parent / "store"))
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# 兼容保留：旧 JSON 文件路径（迁移备份用，运行时不再读写）
HISTORY_FILE = MEMORY_DIR / "plot_history.json"
TASK_FILE = MEMORY_DIR / "task_history.json"
TASK_IMG_DIR = MEMORY_DIR / "task_images"
TASK_IMG_DIR.mkdir(parents=True, exist_ok=True)

STATUS_PENDING = "待审核"
STATUS_PROCESSING = "处理中"
STATUS_COMPLETED = "已完成"
STATUS_CLOSED = "已关闭"
ALL_STATUSES = [STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_CLOSED]

# 标准结构状态码（与中文状态并存，供外部系统按标准字段读取）
_STATUS_CODE_MAP = {
    STATUS_PENDING: "pending",
    STATUS_PROCESSING: "reviewing",
    STATUS_COMPLETED: "published",
    STATUS_CLOSED: "completed",
}


def _plot_key(location: str, crop: str, area: float) -> str:
    loc = (location or "未命名地块").strip()
    return f"{loc}::{crop}::{round(area, 1)}亩"


# ==========================================================================
# 地块历史诊断记录
# ==========================================================================

def record_visit(location: str, crop: str, growth_stage: str, area: float,
                 diagnosis: str, recommendation: str, note: str = "",
                 risk_level: str = "") -> dict:
    """将本次诊断结果写入 SQLite（diagnosis_records 表），并同步地块基础信息。"""
    key = _plot_key(location, crop, area)
    entry = {
        "timestamp": iso_now(),
        "crop": crop,
        "growth_stage": growth_stage,
        "area": area,
        "location": location,
        "diagnosis_summary": diagnosis[:120],
        "recommendation_summary": recommendation[:200],
        "risk_level": risk_level or "未知",
        "note": note,
    }
    repo.create_diagnosis(key, entry)
    repo.upsert_plot(key, location=location, crop=crop, area=area)
    return {"plot_key": key, "entry": entry}


def get_history(location: str, crop: str, area: float, limit: int = 5) -> list[dict]:
    """查询指定地块的历史诊断记录（时间正序，最近 limit 条）。"""
    key = _plot_key(location, crop, area)
    return repo.list_plot_diagnoses(key, limit=limit)


def get_recent_all(limit: int = 10) -> list[dict]:
    """获取所有地块最近的诊断记录（时间倒序）。"""
    return repo.list_diagnoses(limit=limit)


def summarize_history(location: str, crop: str, area: float) -> str:
    """将历史记录压缩成一段文本摘要，供 Agent 注入 Prompt。"""
    records = get_history(location, crop, area, limit=5)
    if not records:
        return ""
    lines = [f"【地块历史 · 共 {len(records)} 次诊断】"]
    for r in records:
        lines.append(
            f"- {r['timestamp'][:16]} | {r['growth_stage']} | 诊断：{r['diagnosis_summary']}"
        )
    return "\n".join(lines)


def clear_history() -> None:
    """清空全部诊断记录（地块档案/农事日志/工单不受影响，与原 JSON 行为一致）。"""
    with repo.db_scope() as conn:
        conn.execute("DELETE FROM diagnosis_records")


def history_stats() -> dict:
    with repo.db_scope() as conn:
        plots = conn.execute(
            "SELECT COUNT(DISTINCT plot_key) FROM diagnosis_records"
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM diagnosis_records").fetchone()[0]
    return {"plots": plots, "total_visits": total}


def get_all_records(crop: str = "", location: str = "", risk_level: str = "",
                    limit: Optional[int] = None) -> list[dict]:
    """获取全部历史诊断记录（支持按作物 / 位置关键词 / 风险等级过滤）。"""
    return repo.list_diagnoses(crop=crop, location=location,
                               risk_level=risk_level, limit=limit)


def list_plots() -> list[dict]:
    """汇总所有地块档案（每地块一行：诊断次数、起止时间、最近风险等）。"""
    with repo.db_scope() as conn:
        agg_rows = conn.execute(
            """
            SELECT plot_key,
                   COUNT(*)            AS visits,
                   MIN(timestamp)      AS first_time,
                   MAX(timestamp)      AS last_time
            FROM diagnosis_records
            GROUP BY plot_key
            """
        ).fetchall()
        latest_rows = conn.execute(
            """
            SELECT * FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY plot_key
                           ORDER BY timestamp DESC, id DESC
                       ) AS rn
                FROM diagnosis_records
            ) WHERE rn = 1
            """
        ).fetchall()

    latest = {r["plot_key"]: dict(r) for r in latest_rows}
    plots: list[dict] = []
    for a in agg_rows:
        key = a["plot_key"]
        last = latest.get(key, {})
        plots.append({
            "plot_key": key,
            "location": last.get("location", ""),
            "crop": last.get("crop", ""),
            "area": last.get("area", 0.0),
            "visits": a["visits"],
            "first_time": a["first_time"],
            "last_time": a["last_time"],
            "last_risk": last.get("risk_level") or "未知",
            "last_summary": last.get("diagnosis_summary", ""),
            "last_recommendation": last.get("recommendation_summary", ""),
        })
    plots.sort(key=lambda p: p["last_time"], reverse=True)
    return plots


def delete_plot(plot_key: str) -> bool:
    """删除指定地块的全部历史档案（诊断记录 + 地块基础信息行）。

    工单（tasks）按原业务规则不受影响；农事日志随档案一并清理。
    """
    with repo.db_scope() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM diagnosis_records WHERE plot_key = ?",
            (plot_key,),
        ).fetchone()[0]
        if cur == 0:
            return False
        conn.execute(
            "DELETE FROM diagnosis_records WHERE plot_key = ?", (plot_key,)
        )
        conn.execute("DELETE FROM farming_logs WHERE plot_key = ?", (plot_key,))
        conn.execute("DELETE FROM plots WHERE plot_key = ?", (plot_key,))
    return True


# ==========================================================================
# 问题工单系统
# ==========================================================================

def _save_task_image(task_id: str, image_bytes: bytes, ext: str = "png") -> str:
    ext = ext.lstrip(".") or "png"
    fname = f"{task_id}.{ext}"
    fpath = TASK_IMG_DIR / fname
    fpath.write_bytes(image_bytes)
    return str(fpath)


def _task_image_path(task_id: str) -> Optional[str]:
    for f in TASK_IMG_DIR.iterdir():
        if f.is_file() and f.stem == task_id:
            return str(f)
    return None


def record_task(location: str, crop: str, growth_stage: str, area: float,
                soil_type: str = "", symptoms: str = "",
                image_bytes: Optional[bytes] = None,
                image_ext: str = "png",
                farmer_name: str = "",
                contact: str = "",
                ai_result: Optional[dict] = None) -> str:
    """
    农户提交 AI 诊断结果后创建一条工单（写入 SQLite tasks 表）。
    返回 task_id。
    """
    task_id = f"tk_{now_cn().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    plot_key = _plot_key(location, crop, area)

    img_path = ""
    if image_bytes:
        try:
            img_path = _save_task_image(task_id, image_bytes, ext=image_ext)
        except Exception:
            img_path = ""

    risk_level = ""
    ai_content = ""
    ai_source = ""
    if ai_result:
        risk_level = (ai_result.get("review") or {}).get("risk_level", "") or ai_result.get("risk_level", "")
        ai_content = ai_result.get("content", "")
        ai_source = ai_result.get("source", "")

    now = iso_now()
    task = {
        "task_id": task_id,
        "plot_key": plot_key,
        "create_time": now,
        "update_time": now,
        "status": STATUS_PENDING,
        "location": location,
        "crop": crop,
        "growth_stage": growth_stage,
        "soil_type": soil_type,
        "area": area,
        "farmer_name": farmer_name,
        "contact": contact,
        "symptoms": symptoms,
        "image_path": img_path,
        "ai_result": {
            "content": ai_content,
            "source": ai_source,
            "risk_level": risk_level or "未知",
            "success": ai_result.get("success", True) if ai_result else True,
        },
        "final_diagnosis": "",
        "final_recommendation": "",
        "reviewer": "",
        "review_notes": "",
        "publish_time": "",
        "close_time": "",
    }
    repo.create_task(task)

    # 农户基础信息同步写入 farmers 表（name+contact 唯一）
    if (farmer_name or "").strip():
        repo.create_farmer(farmer_name, contact)

    return task_id


def list_tasks(status: str = "", plot_key: str = "", crop: str = "",
               keyword: str = "", limit: Optional[int] = None) -> list[dict]:
    """查询工单列表，支持多条件过滤（SQLite 查询，创建时间倒序）。"""
    return repo.list_tasks(status=status, plot_key=plot_key, crop=crop,
                           keyword=keyword, limit=limit)


def get_task(task_id: str) -> Optional[dict]:
    """获取单个工单详情（含 ai_result 嵌套与别名字段，结构同 JSON 版本）。"""
    return repo.get_task(task_id)


def get_task_image_bytes(task_id: str) -> Optional[bytes]:
    """读取工单关联的图片 bytes（图片保存在文件系统）。"""
    p = _task_image_path(task_id)
    if p:
        try:
            return Path(p).read_bytes()
        except OSError:
            return None
    return None


def update_task(task_id: str, *, final_diagnosis: Optional[str] = None,
                final_recommendation: Optional[str] = None,
                reviewer: Optional[str] = None,
                review_notes: Optional[str] = None,
                status: Optional[str] = None) -> bool:
    """农技员编辑工单（改诊断/改建议/加备注/改状态）。"""
    if repo.get_task(task_id) is None:
        return False
    fields: dict = {"update_time": iso_now()}
    if final_diagnosis is not None:
        fields["final_diagnosis"] = final_diagnosis
    if final_recommendation is not None:
        fields["final_recommendation"] = final_recommendation
    if reviewer is not None:
        fields["reviewer"] = reviewer
    if review_notes is not None:
        fields["review_notes"] = review_notes
    if status is not None and status in ALL_STATUSES:
        fields["status"] = status
    repo.update_task(task_id, **fields)
    return True


def save_task_review(task_id: str, reviewer: str, final_diagnosis: str,
                     final_recommendation: str, review_notes: str = "") -> bool:
    """保存审核内容并自动把状态置为 处理中。"""
    return update_task(
        task_id,
        final_diagnosis=final_diagnosis,
        final_recommendation=final_recommendation,
        reviewer=reviewer,
        review_notes=review_notes,
        status=STATUS_PROCESSING,
    )


def publish_task(task_id: str) -> bool:
    """发布建议给农户（状态 → 已完成，记录 publish_time）。"""
    task = repo.get_task(task_id)
    if task is None:
        return False
    if not task.get("final_diagnosis") and not task.get("final_recommendation"):
        return False
    now = iso_now()
    repo.update_task(task_id, status=STATUS_COMPLETED,
                     publish_time=now, update_time=now)
    return True


def close_task(task_id: str) -> bool:
    """关闭工单（不再跟踪）。"""
    if repo.get_task(task_id) is None:
        return False
    now = iso_now()
    repo.update_task(task_id, status=STATUS_CLOSED,
                     close_time=now, update_time=now)
    return True


def delete_task(task_id: str) -> bool:
    """删除工单（同时清理关联图片）。"""
    if not repo.delete_task(task_id):
        return False
    img = _task_image_path(task_id)
    if img:
        try:
            Path(img).unlink(missing_ok=True)
        except OSError:
            pass
    return True


def task_stats() -> dict:
    """工单统计：各状态数量 + 总数 + 高风险待处理数。"""
    raw = repo.task_status_counts()
    counts = {s: 0 for s in ALL_STATUSES}
    for k, v in raw["by_status"].items():
        if k in counts:
            counts[k] = v
    return {
        "total": raw["total"],
        "pending": counts[STATUS_PENDING],
        "processing": counts[STATUS_PROCESSING],
        "completed": counts[STATUS_COMPLETED],
        "closed": counts[STATUS_CLOSED],
        "high_risk_pending": raw["high_risk_pending"],
        "by_status": counts,
    }


__all__ = [
    "record_visit",
    "get_history",
    "get_recent_all",
    "get_all_records",
    "list_plots",
    "delete_plot",
    "summarize_history",
    "clear_history",
    "history_stats",
    "record_task",
    "list_tasks",
    "get_task",
    "get_task_image_bytes",
    "update_task",
    "save_task_review",
    "publish_task",
    "close_task",
    "delete_task",
    "task_stats",
    "STATUS_PENDING",
    "STATUS_PROCESSING",
    "STATUS_COMPLETED",
    "STATUS_CLOSED",
    "ALL_STATUSES",
]
