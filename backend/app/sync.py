from datetime import datetime, timezone

from app.database import get_connection
from app.youtube import fetch_playlists, fetch_playlist_videos
from app.embeddings import EmbeddingService


def sync_user_playlists(db_path: str, user_id: str, access_token: str, refresh_token: str | None = None) -> dict:
    playlists = fetch_playlists(access_token, refresh_token)
    conn = get_connection(db_path)
    embedding_service = EmbeddingService()

    total_videos = 0

    for pl in playlists:
        # Check if playlist needs update (new etag or item count changed)
        existing = conn.execute(
            "SELECT etag, item_count FROM playlists WHERE id = ?", (pl["id"],)
        ).fetchone()

        needs_update = (
            existing is None
            or existing["etag"] != pl["etag"]
            or existing["item_count"] != pl["item_count"]
        )

        # Upsert playlist
        conn.execute(
            """INSERT INTO playlists (id, user_id, title, description, thumbnail_url, item_count, etag)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 title=excluded.title,
                 description=excluded.description,
                 thumbnail_url=excluded.thumbnail_url,
                 item_count=excluded.item_count,
                 etag=excluded.etag""",
            (pl["id"], user_id, pl["title"], pl["description"],
             pl["thumbnail_url"], pl["item_count"], pl["etag"]),
        )

        if not needs_update:
            continue

        # Fetch videos for this playlist
        videos = fetch_playlist_videos(access_token, pl["id"], refresh_token)

        for video in videos:
            # Upsert video
            conn.execute(
                """INSERT INTO videos (id, title, description, channel_name, thumbnail_url, published_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title,
                     description=excluded.description,
                     channel_name=excluded.channel_name,
                     thumbnail_url=excluded.thumbnail_url,
                     published_at=excluded.published_at""",
                (video["video_id"], video["title"], video["description"],
                 video["channel_name"], video["thumbnail_url"], video["published_at"]),
            )

            # Upsert FTS entry
            conn.execute(
                "DELETE FROM videos_fts WHERE video_id = ?", (video["video_id"],)
            )
            conn.execute(
                "INSERT INTO videos_fts (video_id, title, description, channel_name) VALUES (?, ?, ?, ?)",
                (video["video_id"], video["title"], video["description"], video["channel_name"]),
            )

            # Upsert playlist-video link
            conn.execute(
                """INSERT INTO playlist_videos (playlist_id, video_id, position, added_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(playlist_id, video_id) DO UPDATE SET
                     position=excluded.position,
                     added_at=excluded.added_at""",
                (pl["id"], video["video_id"], video["position"], video["added_at"]),
            )

            # Generate embedding if not exists
            existing_emb = conn.execute(
                "SELECT 1 FROM embeddings WHERE video_id = ?", (video["video_id"],)
            ).fetchone()

            if not existing_emb:
                text = f"{video['title']} {video['description']}"
                vector = embedding_service.embed(text)
                conn.execute(
                    "INSERT INTO embeddings (video_id, vector) VALUES (?, ?)",
                    (video["video_id"], embedding_service.vector_to_bytes(vector)),
                )

            total_videos += 1

    # Update last sync timestamp
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE users SET last_sync_at = ? WHERE id = ?", (now, user_id))
    conn.commit()
    conn.close()

    return {"playlists_synced": len(playlists), "videos_synced": total_videos}
