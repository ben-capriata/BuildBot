import sqlite3
from datetime import datetime

from config import DB_PATH


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            priority TEXT DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
            status TEXT DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done')),
            tags TEXT DEFAULT '',
            estimated_minutes INTEGER DEFAULT 60,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS build_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            plan TEXT,
            attempted TEXT,
            worked TEXT,
            didnt_work TEXT,
            surprised TEXT,
            next_time TEXT,
            build_log TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS llm_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            success BOOLEAN DEFAULT 1,
            error TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_task(title, priority="medium"):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (title, priority) VALUES (?, ?)",
        (title, priority),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_active_tasks():
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM tasks WHERE status != 'done' ORDER BY "
        "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def complete_task(task_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), task_id),
    )
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def add_build_session(date, attempted, worked, didnt_work, surprised, next_time, build_log):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO build_sessions (date, attempted, worked, didnt_work, surprised, next_time, build_log) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (date, attempted, worked, didnt_work, surprised, next_time, build_log),
    )
    conn.commit()
    conn.close()


def get_recent_sessions(limit=5):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM build_sessions ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def log_llm_call(provider, model, prompt_tokens=None, completion_tokens=None, success=True, error=None):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO llm_logs (provider, model, prompt_tokens, completion_tokens, success, error) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (provider, model, prompt_tokens, completion_tokens, success, error),
    )
    conn.commit()
    conn.close()
