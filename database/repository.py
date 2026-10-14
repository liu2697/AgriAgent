"""SQLite 数据访问层（repository）：全部业务表的 CRUD 统一入口。

业务层（views / services / agent）不直接执行 SQL，
统一走 memory 服务层 → 本 repository → SQLite。

返回值统一为 dict（与迁移前的 JSON 记录结构保持一致），
保证 memory/history.py、memory/profiles.py 的对外接口零改动。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from database.connection import db_scope


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ==========================================================================
# 农户 farmers
# ==========================================================================

def create_farmer(name: str, contact: str = "") -> int:
    """创建/获取农户（name+contact 唯一，已存在则返回现有 id）。"""
    name, contact = (name or "").strip(), (contact or "").strip()
    now = _now()
    with db_scope() as conn:
        row = conn.execute(
            "SELECT id FROM farmers WHERE name = ? AND contact = ?",
            (name, contact),
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO farmers (name, contact, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (name, contact, now, now),
        )
        return cur.lastrowid


def get_farmer(farmer_id: int) -> Optional[dict]:
    with db_scope() as conn:
        row = conn.execute(
            "SELECT * FROM farmers WHERE id = ?", (farmer_id,)
        ).fetchone()
    return dict(row) if row else None


def list_farmers() -> list[dict]:
    with db_scope() as conn:
        rows = conn.execute(
            "SELECT * FROM farmers ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def count_farmers() -> int:
    with db_scope() as conn:
        return conn.execute("SELECT COUNT(*) FROM farmers").fetchone()[0]


# ==========================================================================
# 地块 plots（含原 profiles.json 并入的档案字段）
# ==========================================================================

def upsert_plot(plot_key: str, location: str = "", crop: str = "",
                area: float = 0.0, **profile_fields) -> None:
    """创建或更新地块基础信息（存在则更新，不存在则创建）。

    空字符串/None 的字段不会覆盖已有值（保护档案字段不被诊断流程清空）。
    """
    now = _now()
    soil = profile_fields.get("soil_type")
    lat = profile_fields.get("latitude")
    lng = profile_fields.get("longitude")
    planting = profile_fields.get("planting_date")
    with db_scope() as conn:
        row = conn.execute(
            "SELECT id FROM plots WHERE plot_key = ?", (plot_key,)
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO plots
                    (plot_key, location, crop, area, soil_type,
                     latitude, longitude, planting_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (plot_key, location, crop, float(area or 0),
                 soil or "", lat or "", lng or "", planting or "", now, now),
            )
        else:
            conn.execute(
                """
                UPDATE plots SET
                    location      = COALESCE(NULLIF(?, ''), location),
                    crop          = COALESCE(NULLIF(?, ''), crop),
                    area          = CASE WHEN ? > 0 THEN ? ELSE area END,
                    soil_type     = COALESCE(?, soil_type),
                    latitude      = COALESCE(?, latitude),
                    longitude     = COALESCE(?, longitude),
                    planting_date = COALESCE(?, planting_date),
                    updated_at    = ?
                WHERE plot_key = ?
                """,
                (location, crop, float(area or 0), float(area or 0),
                 soil, lat, lng, planting, now, plot_key),
            )


def get_plot(plot_key: str) -> Optional[dict]:
    with db_scope() as conn:
        row = conn.execute(
            "SELECT * FROM plots WHERE plot_key = ?", (plot_key,)
        ).fetchone()
    return dict(row) if row else None


def update_plot(plot_key: str, **fields) -> bool:
    """更新地块档案字段（仅允许白名单字段）。"""
    allowed = {"location", "crop", "area", "soil_type",
               "latitude", "longitude", "planting_date"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(_now())
    vals.append(plot_key)
    with db_scope() as conn:
        cur = conn.execute(
            f"UPDATE plots SET {', '.join(sets)} WHERE plot_key = ?", vals
        )
        return cur.rowcount > 0


def delete_plot(plot_key: str) -> bool:
    """删除地块档案行（诊断记录/农事日志由业务层按原规则另行处理）。"""
    with db_scope() as conn:
        cur = conn.execute("DELETE FROM plots WHERE plot_key = ?", (plot_key,))
        return cur.rowcount > 0


def list_plot_keys() -> list[str]:
    """存在诊断记录的地块 key 列表（与迁移前 list_plots 的数据来源一致）。"""
    with db_scope() as conn:
        rows = conn.execute(
            "SELECT DISTINCT plot_key FROM diagnosis_records"
        ).fetchall()
    return [r["plot_key"] for r in rows]


def count_plots() -> int:
    with db_scope() as conn:
        return conn.execute(
            "SELECT COUNT(DISTINCT plot_key) FROM diagnosis_records"
        ).fetchone()[0]


# ==========================================================================
# AI 诊断记录 diagnosis_records
# ==========================================================================

_DIAG_COLS = ("plot_key", "timestamp", "crop", "growth_stage", "area",
              "location", "diagnosis_summary", "recommendation_summary",
              "risk_level", "note")


def create_diagnosis(plot_key: str, entry: dict) -> int:
    """写入一条诊断记录（同 plot_key+timestamp+summary 重复时忽略）。"""
    now = _now()
    vals = {c: entry.get(c, "") for c in _DIAG_COLS}
    vals["plot_key"] = plot_key
    vals["area"] = float(vals.get("area") or 0)
    with db_scope() as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO diagnosis_records
                (plot_key, timestamp, crop, growth_stage, area, location,
                 diagnosis_summary, recommendation_summary, risk_level,
                 note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (vals["plot_key"], vals["timestamp"], vals["crop"],
             vals["growth_stage"], vals["area"], vals["location"],
             vals["diagnosis_summary"], vals["recommendation_summary"],
             vals["risk_level"] or "未知", vals["note"], now),
        )
        return cur.lastrowid


def _diag_row_to_dict(row) -> dict:
    d = dict(row)
    d.pop("id", None)
    d.pop("created_at", None)
    return d


def get_diagnosis(diagnosis_id: int) -> Optional[dict]:
    with db_scope() as conn:
        row = conn.execute(
            "SELECT * FROM diagnosis_records WHERE id = ?", (diagnosis_id,)
        ).fetchone()
    return _diag_row_to_dict(row) if row else None


def list_plot_diagnoses(plot_key: str, limit: Optional[int] = None) -> list[dict]:
    """查询指定地块历史诊断（时间正序；limit 取最近 N 条且保持正序）。"""
    sql = ("SELECT * FROM diagnosis_records WHERE plot_key = ? "
           "ORDER BY timestamp DESC, id DESC")
    if limit:
        sql += f" LIMIT {int(limit)}"
    with db_scope() as conn:
        rows = conn.execute(sql, (plot_key,)).fetchall()
    out = [_diag_row_to_dict(r) for r in rows]
    out.reverse()  # 恢复时间正序，与迁移前 records[-limit:] 行为一致
    return out


def list_diagnoses(crop: str = "", location: str = "", risk_level: str = "",
                   plot_key: str = "", limit: Optional[int] = None) -> list[dict]:
    """全量诊断查询（支持作物/位置关键词/风险等级/地块过滤，时间倒序）。"""
    conds, vals = [], []
    if crop:
        conds.append("crop = ?")
        vals.append(crop)
    if location:
        conds.append("location LIKE ?")
        vals.append(f"%{location}%")
    if risk_level:
        conds.append("risk_level = ?")
        vals.append(risk_level)
    if plot_key:
        conds.append("plot_key = ?")
        vals.append(plot_key)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    sql = (f"SELECT * FROM diagnosis_records {where} "
           "ORDER BY timestamp DESC, id DESC")
    if limit:
        sql += f" LIMIT {int(limit)}"
    with db_scope() as conn:
        rows = conn.execute(sql, vals).fetchall()
    return [_diag_row_to_dict(r) for r in rows]


def delete_plot_diagnoses(plot_key: str) -> int:
    with db_scope() as conn:
        cur = conn.execute(
            "DELETE FROM diagnosis_records WHERE plot_key = ?", (plot_key,)
        )
        return cur.rowcount


def count_diagnoses() -> int:
    with db_scope() as conn:
        return conn.execute("SELECT COUNT(*) FROM diagnosis_records").fetchone()[0]


def count_high_risk_plots() -> int:
    """高风险地块数（最近一次诊断为高风险的 distinct 地块）。"""
    with db_scope() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT plot_key, risk_level,
                       ROW_NUMBER() OVER (
                           PARTITION BY plot_key
                           ORDER BY timestamp DESC, id DESC
                       ) AS rn
                FROM diagnosis_records
            ) WHERE rn = 1 AND risk_level = '高'
            """
        ).fetchone()
    return row[0]


def plot_latest_risk_map() -> dict[str, str]:
    """每个地块最近一次诊断的风险等级。"""
    with db_scope() as conn:
        rows = conn.execute(
            """
            SELECT plot_key, risk_level FROM (
                SELECT plot_key, risk_level,
                       ROW_NUMBER() OVER (
                           PARTITION BY plot_key
                           ORDER BY timestamp DESC, id DESC
                       ) AS rn
                FROM diagnosis_records
            ) WHERE rn = 1
            """
        ).fetchall()
    return {r["plot_key"]: r["risk_level"] for r in rows}


# ==========================================================================
# 农事日志 farming_logs
# ==========================================================================

def create_farming_log(plot_key: str, log_type: str, note: str,
                       timestamp: Optional[str] = None) -> dict:
    """追加一条农事日志（同 plot_key+timestamp+type 重复时忽略）。"""
    ts = timestamp or _now()
    note = (note or "").strip()[:200]
    with db_scope() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO farming_logs
                (plot_key, timestamp, type, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (plot_key, ts, log_type, note, _now()),
        )
    return {"timestamp": ts, "type": log_type, "note": note}


def list_farming_logs(plot_key: str) -> list[dict]:
    """获取地块全部农事日志（时间正序）。"""
    with db_scope() as conn:
        rows = conn.execute(
            "SELECT timestamp, type, note FROM farming_logs "
            "WHERE plot_key = ? ORDER BY timestamp ASC, id ASC",
            (plot_key,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_farming_logs(plot_key: str) -> int:
    with db_scope() as conn:
        cur = conn.execute(
            "DELETE FROM farming_logs WHERE plot_key = ?", (plot_key,)
        )
        return cur.rowcount


def count_farming_logs() -> int:
    with db_scope() as conn:
        return conn.execute("SELECT COUNT(*) FROM farming_logs").fetchone()[0]


# ==========================================================================
# 工单 tasks
# ==========================================================================

_STATUS_CODE_MAP = {
    "待审核": "pending",
    "处理中": "reviewing",
    "已完成": "published",
    "已关闭": "completed",
}


def create_task(task: dict) -> str:
    """创建工单（task_id 唯一，重复导入时忽略）。"""
    now = _now()
    ai = task.get("ai_result") or {}
    with db_scope() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO tasks
                (task_id, plot_key, status, location, crop, growth_stage,
                 soil_type, area, farmer_name, contact, symptoms, image_path,
                 ai_content, ai_source, ai_risk_level, ai_success,
                 final_diagnosis, final_recommendation, reviewer, review_notes,
                 create_time, update_time, publish_time, close_time,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.get("task_id", ""),
                task.get("plot_key", ""),
                task.get("status", "待审核"),
                task.get("location", ""),
                task.get("crop", ""),
                task.get("growth_stage", ""),
                task.get("soil_type", ""),
                float(task.get("area") or 0),
                task.get("farmer_name", ""),
                task.get("contact", ""),
                task.get("symptoms", ""),
                task.get("image_path", ""),
                ai.get("content", ""),
                ai.get("source", ""),
                ai.get("risk_level", "未知") or "未知",
                1 if ai.get("success", True) else 0,
                task.get("final_diagnosis", ""),
                task.get("final_recommendation", ""),
                task.get("reviewer", ""),
                task.get("review_notes", ""),
                task.get("create_time", "") or now,
                task.get("update_time", "") or now,
                task.get("publish_time", ""),
                task.get("close_time", ""),
                now, now,
            ),
        )
    return task.get("task_id", "")


def _task_row_to_dict(row) -> dict:
    """还原为迁移前的工单 dict 结构（含 ai_result 嵌套与别名字段）。"""
    d = dict(row)
    ai_content = d.pop("ai_content", "")
    ai_source = d.pop("ai_source", "")
    ai_risk = d.pop("ai_risk_level", "未知")
    ai_success = bool(d.pop("ai_success", 1))
    d.pop("id", None)
    d.pop("created_at", None)
    d.pop("updated_at", None)

    d["ai_result"] = {
        "content": ai_content,
        "source": ai_source,
        "risk_level": ai_risk or "未知",
        "success": ai_success,
    }
    # 标准结构别名字段：与迁移前 JSON 结构并存，保证外部读取兼容
    d["image"] = d.get("image_path", "") or ""
    d["diagnosis"] = ai_content
    d["risk_level"] = ai_risk or "未知"
    d["created_time"] = d.get("create_time", "")
    d["status_code"] = _STATUS_CODE_MAP.get(d.get("status", ""), d.get("status", ""))
    return d


def get_task(task_id: str) -> Optional[dict]:
    with db_scope() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    return _task_row_to_dict(row) if row else None


def update_task(task_id: str, **fields) -> bool:
    """更新工单字段（仅允许白名单字段）。"""
    allowed = {
        "final_diagnosis", "final_recommendation", "reviewer", "review_notes",
        "status", "publish_time", "close_time", "update_time",
    }
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(_now())
    vals.append(task_id)
    with db_scope() as conn:
        cur = conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = ?", vals
        )
        return cur.rowcount > 0


def delete_task(task_id: str) -> bool:
    with db_scope() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        return cur.rowcount > 0


def list_tasks(status: str = "", plot_key: str = "", crop: str = "",
               keyword: str = "", limit: Optional[int] = None) -> list[dict]:
    """工单列表查询（多条件过滤，创建时间倒序）。"""
    conds, vals = [], []
    if status:
        conds.append("status = ?")
        vals.append(status)
    if plot_key:
        conds.append("plot_key = ?")
        vals.append(plot_key)
    if crop:
        conds.append("crop = ?")
        vals.append(crop)
    if keyword:
        kw = f"%{keyword.lower()}%"
        conds.append(
            "(LOWER(plot_key) LIKE ? OR LOWER(crop) LIKE ? OR LOWER(location) LIKE ? "
            "OR LOWER(symptoms) LIKE ? OR LOWER(farmer_name) LIKE ? "
            "OR LOWER(final_diagnosis) LIKE ? OR LOWER(final_recommendation) LIKE ? "
            "OR LOWER(ai_content) LIKE ?)"
        )
        vals.extend([kw] * 8)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    sql = f"SELECT * FROM tasks {where} ORDER BY create_time DESC, id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with db_scope() as conn:
        rows = conn.execute(sql, vals).fetchall()
    return [_task_row_to_dict(r) for r in rows]


def count_tasks() -> int:
    with db_scope() as conn:
        return conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]


def task_status_counts() -> dict:
    """各状态工单数量 + 总数 + 高风险待处理数。"""
    with db_scope() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM tasks GROUP BY status"
        ).fetchall()
        high = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status IN ('待审核', '处理中') "
            "AND ai_risk_level = '高'"
        ).fetchone()[0]
    by_status = {r["status"]: r["c"] for r in rows}
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "high_risk_pending": high,
    }


def list_task_ids() -> list[str]:
    with db_scope() as conn:
        rows = conn.execute("SELECT task_id FROM tasks").fetchall()
    return [r["task_id"] for r in rows]
