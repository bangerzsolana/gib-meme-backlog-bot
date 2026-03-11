import sqlite3
import os
from datetime import datetime

# Use /data/backlog.db if /data exists (Railway volume), else local backlog.db
if os.path.isdir("/data"):
    DB_PATH = "/data/backlog.db"
else:
    DB_PATH = "backlog.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed_admin: str = ""):
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            chat_id INTEGER,
            added_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            description TEXT,
            image_file_id TEXT,
            added_by TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    if seed_admin:
        seed_admin = seed_admin.lstrip("@").lower()
        try:
            c.execute(
                "INSERT OR IGNORE INTO admins (username, added_by) VALUES (?, ?)",
                (seed_admin, "seed"),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass

    conn.close()


# --- Admin functions ---

def is_admin(username: str) -> bool:
    if not username:
        return False
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM admins WHERE username = ?", (username.lower(),)
    ).fetchone()
    conn.close()
    return row is not None


def add_admin(username: str, added_by: str) -> bool:
    username = username.lstrip("@").lower()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO admins (username, added_by) VALUES (?, ?)",
            (username, added_by),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def remove_admin(username: str) -> bool:
    username = username.lstrip("@").lower()
    conn = get_conn()
    cur = conn.execute("DELETE FROM admins WHERE username = ?", (username,))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def update_admin_chat_id(username: str, chat_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE admins SET chat_id = ? WHERE username = ?",
        (chat_id, username.lower()),
    )
    conn.commit()
    conn.close()


def list_admins() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT username, chat_id, added_by, created_at FROM admins ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Settings functions ---

def get_setting(key: str) -> str | None:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


# --- Items functions ---

def add_item(
    category: str,
    description: str,
    image_file_id: str | None,
    added_by: str,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO items (category, description, image_file_id, added_by)
        VALUES (?, ?, ?, ?)
        """,
        (category, description, image_file_id, added_by),
    )
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return item_id
