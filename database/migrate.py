"""JSON → SQLite 一次性迁移脚本。

用法：
    python database/migrate.py          # 迁移 memory/store/ 下的业务 JSON
    python -c "from database.migrate import migrate_json_to_sqlite; migrate_json_to_sqlite()"

规则：
- 原 JSON 文件保留不动（作为迁移备份）。
- 通过 UNIQUE 索引 + INSERT OR IGNORE 防止重复导入，可安全重复执行。
- 单条异常数据只记录 warning，不中断整体迁移；每个文件独立事务。
- 迁移完成后输出各表统计。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# 支持 `python database/migrate.py` 直接运行：将项目根加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import db_scope, get_db_path
from timeutil import iso_now

DEFAULT_STORE_DIR = PROJECT_ROOT / "memory" / "store"

# 业务 JSON → 迁移源标识
_SOURCE_PLOT_HISTORY = "plot_history.json"
_SOURCE_TASK_HISTORY = "task_history.json"
_SOURCE_PROFILES = "plot_profiles.json"


def _now() -> str:
    return iso_now()


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARNING] 读取失败 {path.name}: {e}")
        return None


def _migrate_plot_history(store: dict, warnings: list) -> int:
    """plot_history.json: {plot_key: [entry, ...]} → diagnosis_records + plots。"""
    if not isinstance(store, dict):
        warnings.append(f"{_SOURCE_PLOT_HISTORY}: 顶层结构不是 dict，跳过")
        return 0
    count = 0
    with db_scope() as conn:
        for plot_key, entries in store.items():
            if not isinstance(entries, list):
                warnings.append(f"plot_history: {plot_key} 的值不是列表，跳过")
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    warnings.append(f"plot_history: {plot_key} 存在非 dict 记录，跳过")
                    continue
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO diagnosis_records
                            (plot_key, timestamp, crop, growth_stage, area,
                             location, diagnosis_summary, recommendation_summary,
                             risk_level, note, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            plot_key,
                            str(entry.get("timestamp", "")),
                            str(entry.get("crop", "")),
                            str(entry.get("growth_stage", "")),
                            float(entry.get("area") or 0),
                            str(entry.get("location", "")),
                            str(entry.get("diagnosis_summary", "")),
                            str(entry.get("recommendation_summary", "")),
                            str(entry.get("risk_level") or "未知"),
                            str(entry.get("note", "")),
                            _now(),
                        ),
                    )
                    count += 1
                except (TypeError, ValueError, KeyError) as e:
                    warnings.append(f"plot_history: {plot_key} 一条记录跳过（{e}）")

            # 同步地块基础信息（取该地块最新一条记录的 location/crop/area）
            try:
                valid = [e for e in entries if isinstance(e, dict) and e.get("timestamp")]
                if valid:
                    last = sorted(valid, key=lambda e: e.get("timestamp", ""))[-1]
                    conn.execute(
                        """
                        INSERT INTO plots
                            (plot_key, location, crop, area, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(plot_key) DO UPDATE SET
                            location   = COALESCE(NULLIF(excluded.location, ''), plots.location),
                            crop       = COALESCE(NULLIF(excluded.crop, ''), plots.crop),
                            area       = CASE WHEN excluded.area > 0 THEN excluded.area ELSE plots.area END,
                            updated_at = excluded.updated_at
                        """,
                        (plot_key, str(last.get("location", "")),
                         str(last.get("crop", "")), float(last.get("area") or 0),
                         _now(), _now()),
                    )
            except (TypeError, ValueError) as e:
                warnings.append(f"plot_history: {plot_key} 地块基础信息同步失败（{e}）")
    return count


def _migrate_task_history(store: dict, warnings: list) -> int:
    """task_history.json: {task_id: task} → tasks + farmers。"""
    if not isinstance(store, dict):
        warnings.append(f"{_SOURCE_TASK_HISTORY}: 顶层结构不是 dict，跳过")
        return 0
    count = 0
    now = _now()
    with db_scope() as conn:
        for task_id, task in store.items():
            if not isinstance(task, dict):
                warnings.append(f"task_history: {task_id} 不是 dict，跳过")
                continue
            try:
                ai = task.get("ai_result") or {}
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
                        str(task.get("task_id", task_id)),
                        str(task.get("plot_key", "")),
                        str(task.get("status", "待审核")),
                        str(task.get("location", "")),
                        str(task.get("crop", "")),
                        str(task.get("growth_stage", "")),
                        str(task.get("soil_type", "")),
                        float(task.get("area") or 0),
                        str(task.get("farmer_name", "")),
                        str(task.get("contact", "")),
                        str(task.get("symptoms", "")),
                        str(task.get("image_path", "")),
                        str(ai.get("content", "")),
                        str(ai.get("source", "")),
                        str(ai.get("risk_level") or "未知"),
                        1 if ai.get("success", True) else 0,
                        str(task.get("final_diagnosis", "")),
                        str(task.get("final_recommendation", "")),
                        str(task.get("reviewer", "")),
                        str(task.get("review_notes", "")),
                        str(task.get("create_time", "") or now),
                        str(task.get("update_time", "") or now),
                        str(task.get("publish_time", "")),
                        str(task.get("close_time", "")),
                        now, now,
                    ),
                )
                count += 1

                # 农户信息提炼 → farmers 表
                fname = str(task.get("farmer_name", "")).strip()
                if fname:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO farmers (name, contact, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (fname, str(task.get("contact", "")).strip(), now, now),
                    )
            except (TypeError, ValueError) as e:
                warnings.append(f"task_history: {task_id} 迁移失败（{e}）")
    return count


def _migrate_profiles(store: dict, warnings: list) -> int:
    """plot_profiles.json: {plot_key: {档案字段 + logs}} → plots 档案字段 + farming_logs。"""
    if not isinstance(store, dict):
        warnings.append(f"{_SOURCE_PROFILES}: 顶层结构不是 dict，跳过")
        return 0
    now = _now()
    log_count = 0
    with db_scope() as conn:
        for plot_key, profile in store.items():
            if not isinstance(profile, dict):
                warnings.append(f"profiles: {plot_key} 不是 dict，跳过")
                continue
            try:
                conn.execute(
                    """
                    INSERT INTO plots
                        (plot_key, location, crop, area, soil_type,
                         latitude, longitude, planting_date, created_at, updated_at)
                    VALUES (?, '', '', 0, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(plot_key) DO UPDATE SET
                        soil_type     = COALESCE(NULLIF(excluded.soil_type, ''), plots.soil_type),
                        latitude      = COALESCE(NULLIF(excluded.latitude, ''), plots.latitude),
                        longitude     = COALESCE(NULLIF(excluded.longitude, ''), plots.longitude),
                        planting_date = COALESCE(NULLIF(excluded.planting_date, ''), plots.planting_date),
                        updated_at    = excluded.updated_at
                    """,
                    (plot_key,
                     str(profile.get("soil_type", "")),
                     str(profile.get("latitude", "")),
                     str(profile.get("longitude", "")),
                     str(profile.get("planting_date", "")),
                     now, now),
                )
            except (TypeError, ValueError) as e:
                warnings.append(f"profiles: {plot_key} 档案字段迁移失败（{e}）")

            logs = profile.get("logs")
            if isinstance(logs, list):
                for lg in logs:
                    try:
                        # 字段映射：演示数据 JSON 使用 log_type，运行时结构使用 type
                        log_type = str(lg.get("type") or lg.get("log_type") or "巡田")
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO farming_logs
                                (plot_key, timestamp, type, note, created_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (plot_key,
                             str(lg.get("timestamp", "")),
                             log_type,
                             str(lg.get("note", "")),
                             now),
                        )
                        log_count += 1
                    except (TypeError, ValueError) as e:
                        warnings.append(f"profiles: {plot_key} 一条农事日志跳过（{e}）")
    return log_count


def _record_meta(conn, source: str, count: int) -> None:
    conn.execute(
        """
        INSERT INTO migration_meta (source_file, imported_at, record_count)
        VALUES (?, ?, ?)
        ON CONFLICT(source_file) DO UPDATE SET
            imported_at = excluded.imported_at,
            record_count = excluded.record_count
        """,
        (source, _now(), count),
    )


def migrate_json_to_sqlite(store_dir: Path | str = DEFAULT_STORE_DIR,
                           verbose: bool = True) -> dict:
    """将 memory/store/ 下的业务 JSON 数据迁移到 SQLite。

    返回迁移统计 dict；原 JSON 文件保留不动；可安全重复执行（幂等）。
    """
    store_dir = Path(store_dir)
    warnings: list[str] = []

    # 前置：确保表结构存在
    from database.schema import init_db
    init_db()

    plot_store = _load_json(store_dir / _SOURCE_PLOT_HISTORY)
    task_store = _load_json(store_dir / _SOURCE_TASK_HISTORY)
    profile_store = _load_json(store_dir / _SOURCE_PROFILES)

    n_diag = _migrate_plot_history(plot_store, warnings) if plot_store else 0
    n_tasks = _migrate_task_history(task_store, warnings) if task_store else 0
    n_logs = _migrate_profiles(profile_store, warnings) if profile_store else 0

    # 记录迁移元数据
    with db_scope() as conn:
        if plot_store:
            _record_meta(conn, _SOURCE_PLOT_HISTORY, n_diag)
        if task_store:
            _record_meta(conn, _SOURCE_TASK_HISTORY, n_tasks)
        if profile_store:
            _record_meta(conn, _SOURCE_PROFILES, n_logs)

    # 输出统计
    with db_scope() as conn:
        stats = {
            "plots": conn.execute(
                "SELECT COUNT(DISTINCT plot_key) FROM diagnosis_records"
            ).fetchone()[0],
            "diagnosis_records": conn.execute(
                "SELECT COUNT(*) FROM diagnosis_records"
            ).fetchone()[0],
            "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
            "farmers": conn.execute("SELECT COUNT(*) FROM farmers").fetchone()[0],
            "farming_logs": conn.execute(
                "SELECT COUNT(*) FROM farming_logs"
            ).fetchone()[0],
        }

    if verbose:
        db = get_db_path()
        print("=" * 52)
        print("JSON → SQLite 迁移完成")
        print(f"数据库文件: {db}")
        print("-" * 52)
        print(f"plots:            {stats['plots']}")
        print(f"diagnosis_records:{stats['diagnosis_records']}")
        print(f"tasks:            {stats['tasks']}")
        print(f"farmers:          {stats['farmers']}")
        print(f"farming_logs:     {stats['farming_logs']}")
        if warnings:
            print("-" * 52)
            print(f"警告 {len(warnings)} 条：")
            for w in warnings:
                print(f"  [WARNING] {w}")
        print("=" * 52)

    result = dict(stats)
    result["warnings"] = warnings
    return result


if __name__ == "__main__":
    if "--check" in sys.argv:
        from database.schema import check_database
        info = check_database()
        print(info)
    else:
        migrate_json_to_sqlite()
