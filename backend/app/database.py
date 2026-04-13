import sqlite3


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            picture TEXT,
            access_token_encrypted BLOB,
            refresh_token_encrypted BLOB,
            last_sync_at TEXT
        );

        CREATE TABLE IF NOT EXISTS playlists (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            thumbnail_url TEXT DEFAULT '',
            item_count INTEGER DEFAULT 0,
            etag TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            channel_name TEXT DEFAULT '',
            thumbnail_url TEXT DEFAULT '',
            published_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS playlist_videos (
            playlist_id TEXT NOT NULL,
            video_id TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            added_at TEXT DEFAULT '',
            PRIMARY KEY (playlist_id, video_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id),
            FOREIGN KEY (video_id) REFERENCES videos(id)
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            video_id TEXT PRIMARY KEY,
            vector BLOB NOT NULL,
            FOREIGN KEY (video_id) REFERENCES videos(id)
        );
    """)

    # FTS5 virtual table for full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts
        USING fts5(video_id, title, description, channel_name, content='')
    """)

    conn.commit()
    conn.close()
