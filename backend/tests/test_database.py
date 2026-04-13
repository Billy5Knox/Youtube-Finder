import sqlite3
from app.database import init_db, get_connection


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]

    assert "users" in tables
    assert "playlists" in tables
    assert "videos" in tables
    assert "playlist_videos" in tables
    assert "embeddings" in tables
    conn.close()


def test_init_db_creates_fts5_index(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='videos_fts'"
    )
    assert cursor.fetchone() is not None
    conn.close()
