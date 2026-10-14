"""SQLite 连接管理。

- 数据库文件统一使用 data/agragent.db（可用环境变量 AGENT_DB_PATH 覆盖，供测试使用）。
- 每次操作创建独立连接，不做全局长期共享连接对象。
- 提供 db_scope() 上下文管理器统一处理 commit / rollback / close。
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_db_path() -> Path:
    """获取数据库文件路径（默认 data/agragent.db，可被 AGENT_DB_PATH 覆盖）。"""
    env = os.environ.get("AGENT_DB_PATH")
    if env:
        return Path(env)
    return PROJECT_ROOT / "data" / "agragent.db"


# 便捷引用（模块导入时的默认路径；运行时请使用 get_db_path()）
DB_PATH = get_db_path()


def get_connection() -> sqlite3.Connection:
    """创建一个新的 SQLite 连接（row_factory 按字段名访问）。

    调用方负责 commit / close；推荐使用 db_scope() 自动管理。
    """
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_scope():
    """统一的事务作用域：正常退出 commit，异常 rollback，最后 close。"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


__all__ = ["get_db_path", "DB_PATH", "get_connection", "db_scope"]
