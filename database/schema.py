"""SQLite 表结构定义与初始化。

设计说明：
- 时间字段统一 ISO 8601 字符串（如 2026-09-25T22:30:00）。
- plots 表将原 profiles.json 中的地块档案字段（土壤/经纬度/播种时间）合并保存，
  因为其与地块是严格 1:1 关系，独立建表没有业务意义。
- 农事日志从 profiles.json 的嵌套 logs 数组拆出为独立 farming_logs 表。
- 工单 ai_result 拆为 ai_content / ai_source / ai_risk_level / ai_success 结构化字段。
- UNIQUE 索引同时承担 JSON→SQLite 迁移的防重复导入职责（INSERT OR IGNORE）。
- 图片不入库：tasks.image_path 仅保存文件系统引用。
"""
from __future__ import annotations

from database.connection import db_scope, get_db_path

SCHEMA_SQL = """
-- ------------------------------------------------------------------
-- 农户表（从工单提交人信息提炼：农户基础信息）
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS farmers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL DEFAULT '',
    contact     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(name, contact)
);

-- ------------------------------------------------------------------
-- 地块表（plot_key 为业务主键；档案字段由 profiles.json 并入）
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_key      TEXT NOT NULL UNIQUE,
    location      TEXT NOT NULL DEFAULT '',
    crop          TEXT NOT NULL DEFAULT '',
    area          REAL NOT NULL DEFAULT 0,
    soil_type     TEXT NOT NULL DEFAULT '',
    latitude      TEXT NOT NULL DEFAULT '',
    longitude     TEXT NOT NULL DEFAULT '',
    planting_date TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plots_location ON plots(location);
CREATE INDEX IF NOT EXISTS idx_plots_crop ON plots(crop);

-- ------------------------------------------------------------------
-- AI 诊断记录表（原 plot_history.json 的 entries）
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS diagnosis_records (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_key               TEXT NOT NULL,
    timestamp              TEXT NOT NULL,
    crop                   TEXT NOT NULL DEFAULT '',
    growth_stage           TEXT NOT NULL DEFAULT '',
    area                   REAL NOT NULL DEFAULT 0,
    location               TEXT NOT NULL DEFAULT '',
    diagnosis_summary      TEXT NOT NULL DEFAULT '',
    recommendation_summary TEXT NOT NULL DEFAULT '',
    content                TEXT NOT NULL DEFAULT '',
    risk_level             TEXT NOT NULL DEFAULT '未知',
    note                   TEXT NOT NULL DEFAULT '',
    created_at             TEXT NOT NULL,
    UNIQUE(plot_key, timestamp, diagnosis_summary, note)
);
CREATE INDEX IF NOT EXISTS idx_diag_plot_ts ON diagnosis_records(plot_key, timestamp);
CREATE INDEX IF NOT EXISTS idx_diag_risk ON diagnosis_records(risk_level);
CREATE INDEX IF NOT EXISTS idx_diag_timestamp ON diagnosis_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_diag_crop ON diagnosis_records(crop);

-- ------------------------------------------------------------------
-- 农事日志表（原 profiles.json 内嵌 logs 数组拆表）
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS farming_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_key   TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    type       TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(plot_key, timestamp, type, note)
);
CREATE INDEX IF NOT EXISTS idx_flog_plot_ts ON farming_logs(plot_key, timestamp);

-- ------------------------------------------------------------------
-- 农技员工单表（原 task_history.json）
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id             TEXT NOT NULL UNIQUE,
    plot_key            TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT '待审核',
    location            TEXT NOT NULL DEFAULT '',
    crop                TEXT NOT NULL DEFAULT '',
    growth_stage        TEXT NOT NULL DEFAULT '',
    soil_type           TEXT NOT NULL DEFAULT '',
    area                REAL NOT NULL DEFAULT 0,
    farmer_name         TEXT NOT NULL DEFAULT '',
    contact             TEXT NOT NULL DEFAULT '',
    symptoms            TEXT NOT NULL DEFAULT '',
    image_path          TEXT NOT NULL DEFAULT '',
    ai_content          TEXT NOT NULL DEFAULT '',
    ai_source           TEXT NOT NULL DEFAULT '',
    ai_risk_level       TEXT NOT NULL DEFAULT '未知',
    ai_success          INTEGER NOT NULL DEFAULT 1,
    final_diagnosis     TEXT NOT NULL DEFAULT '',
    final_recommendation TEXT NOT NULL DEFAULT '',
    reviewer            TEXT NOT NULL DEFAULT '',
    review_notes        TEXT NOT NULL DEFAULT '',
    create_time         TEXT NOT NULL,
    update_time         TEXT NOT NULL,
    publish_time        TEXT NOT NULL DEFAULT '',
    close_time          TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_plot ON tasks(plot_key);
CREATE INDEX IF NOT EXISTS idx_tasks_create_time ON tasks(create_time);
CREATE INDEX IF NOT EXISTS idx_tasks_farmer ON tasks(farmer_name);

-- ------------------------------------------------------------------
-- 迁移元数据表（记录 JSON → SQLite 迁移历史，支持增量迁移审计）
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS migration_meta (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file  TEXT NOT NULL UNIQUE,
    imported_at  TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0
);
"""

_CORE_TABLES = ("farmers", "plots", "diagnosis_records", "farming_logs", "tasks")


def init_db() -> None:
    """初始化数据库：自动创建 data/ 目录、数据库文件、缺失的表与索引。

    使用 CREATE TABLE IF NOT EXISTS，重复启动不会破坏已有数据。
    """
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with db_scope() as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_columns(conn)


def _ensure_columns(conn) -> None:
    """增量迁移：给旧库补上后加的列（幂等，不影响已有数据）。

    为什么需要：CREATE TABLE IF NOT EXISTS 对已存在的表不会新增列，
    旧库缺少 diagnosis_records.content 时，历史诊断就只能导出被截断的摘要。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(diagnosis_records)")}
    if "content" not in cols:
        conn.execute("ALTER TABLE diagnosis_records "
                     "ADD COLUMN content TEXT NOT NULL DEFAULT ''")


def check_database() -> dict:
    """数据库健康检查：文件 / 表 / 各表记录数 / 读写测试。"""
    path = get_db_path()
    result = {
        "ok": False,
        "path": str(path),
        "exists": path.exists(),
        "tables": {},
        "writable": False,
        "error": "",
    }
    try:
        with db_scope() as conn:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for t in _CORE_TABLES:
                if t in names:
                    result["tables"][t] = conn.execute(
                        f"SELECT COUNT(*) FROM {t}"
                    ).fetchone()[0]
                else:
                    result["tables"][t] = None

            # 读写测试（探针表，用后即删）
            conn.execute("CREATE TABLE IF NOT EXISTS _health_probe (v TEXT)")
            conn.execute("INSERT INTO _health_probe (v) VALUES ('ok')")
            row = conn.execute("SELECT v FROM _health_probe LIMIT 1").fetchone()
            conn.execute("DROP TABLE _health_probe")
            result["writable"] = bool(row and row[0] == "ok")
        result["ok"] = result["writable"] and all(
            v is not None for v in result["tables"].values()
        )
    except Exception as e:  # noqa: BLE001 — 健康检查需要兜底
        result["error"] = str(e)
    return result


__all__ = ["SCHEMA_SQL", "init_db", "check_database"]
