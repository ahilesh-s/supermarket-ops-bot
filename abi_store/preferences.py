"""preferences.py — standing owner preferences (default payment mode,
preferred brand, shop name/GSTIN for invoices). Lives in the DB, not the
conversation, so it survives a /new chat."""

from .db import get_connection


def get_preference(key: str, default=None):
    conn = get_connection()
    row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_preference(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO preferences (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()
