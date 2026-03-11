import psycopg2
import psycopg2.extras

import config


def get_conn():
    conn = psycopg2.connect(config.DATABASE_URL)
    return conn


def init_db(seed_admin: str = ""):
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            chat_id BIGINT,
            added_by TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            image_file_id TEXT,
            added_by TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()

    if seed_admin:
        seed_admin = seed_admin.lstrip("@").lower()
        try:
            c.execute(
                "INSERT INTO admins (username, added_by) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING",
                (seed_admin, "seed"),
            )
            conn.commit()
        except Exception:
            conn.rollback()

    c.close()
    conn.close()


# --- Admin functions ---

def is_admin(username: str) -> bool:
    if not username:
        return False
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM admins WHERE username = %s", (username.lower(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def add_admin(username: str, added_by: str) -> bool:
    username = username.lstrip("@").lower()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO admins (username, added_by) VALUES (%s, %s)",
            (username, added_by),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        conn.close()
        return False


def remove_admin(username: str) -> bool:
    username = username.lstrip("@").lower()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE username = %s", (username,))
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    return affected > 0


def update_admin_chat_id(username: str, chat_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE admins SET chat_id = %s WHERE username = %s",
        (chat_id, username.lower()),
    )
    conn.commit()
    cur.close()
    conn.close()


def list_admins() -> list:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT username, chat_id, added_by, created_at FROM admins ORDER BY created_at"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# --- Settings functions ---

def get_setting(key: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["value"] if row else None


def set_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, value),
    )
    conn.commit()
    cur.close()
    conn.close()


# --- Items functions ---

def add_item(
    category: str,
    description: str,
    image_file_id: str | None,
    added_by: str,
) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO items (category, description, image_file_id, added_by)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (category, description, image_file_id, added_by),
    )
    conn.commit()
    item_id = cur.fetchone()[0]
    cur.close()
    conn.close()
    return item_id
