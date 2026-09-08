"""Runtime data must never be written into an installed package."""
import os
from pathlib import Path
import subprocess
import sys


def test_explicit_data_root(tmp_path):
    root = tmp_path / "shop with spaces"
    env = {**os.environ, "SUPERMARKET_DATA_DIR": str(root)}
    result = subprocess.run(
        [sys.executable, "-c", "from abi_store.db import init_db; init_db()"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (root / "database" / "stock.db").is_file()
    assert (root / "database" / "khata.db").is_file()


def test_transaction_uses_current_configured_database(tmp_path, monkeypatch):
    from abi_store import db
    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "STOCK_DB_PATH", tmp_path / "stock.db")
    monkeypatch.setattr(db, "KHATA_DB_PATH", tmp_path / "khata.db")
    db.init_db()
    with db.transaction() as conn:
        conn.execute("INSERT INTO preferences VALUES ('probe', 'isolated')")
    conn = db.get_connection()
    try:
        assert conn.execute("SELECT value FROM preferences WHERE key='probe'").fetchone()[0] == "isolated"
    finally:
        conn.close()
