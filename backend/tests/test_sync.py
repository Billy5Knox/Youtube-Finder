from unittest.mock import patch, MagicMock
from app.database import get_connection
from app.sync import sync_user_playlists


MOCK_PLAYLISTS = [
    {
        "id": "pl1",
        "title": "Web Dev",
        "description": "Web tutorials",
        "thumbnail_url": "https://example.com/pl1.jpg",
        "item_count": 2,
        "etag": "etag1",
    },
]

MOCK_VIDEOS = [
    {
        "video_id": "v1",
        "title": "React Tutorial",
        "description": "Learn React",
        "channel_name": "Fireship",
        "thumbnail_url": "https://example.com/v1.jpg",
        "published_at": "2024-01-01T00:00:00Z",
        "position": 0,
        "added_at": "2024-06-01T00:00:00Z",
    },
    {
        "video_id": "v2",
        "title": "CSS Grid Guide",
        "description": "Master CSS grid",
        "channel_name": "Kevin Powell",
        "thumbnail_url": "https://example.com/v2.jpg",
        "published_at": "2024-02-01T00:00:00Z",
        "position": 1,
        "added_at": "2024-06-02T00:00:00Z",
    },
]


@patch("app.sync.EmbeddingService")
@patch("app.sync.fetch_playlist_videos")
@patch("app.sync.fetch_playlists")
def test_sync_stores_playlists_and_videos(mock_fetch_pl, mock_fetch_vids, mock_embed, db_path):
    mock_fetch_pl.return_value = MOCK_PLAYLISTS
    mock_fetch_vids.return_value = MOCK_VIDEOS

    mock_service = MagicMock()
    mock_embed.return_value = mock_service
    import numpy as np
    mock_service.embed.return_value = np.zeros(384, dtype=np.float32)
    mock_service.vector_to_bytes.return_value = np.zeros(384, dtype=np.float32).tobytes()

    # Insert a user first
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO users (id, email, name, picture, access_token_encrypted) VALUES (?, ?, ?, ?, ?)",
        ("user1", "test@test.com", "Test", "", b"fake_token"),
    )
    conn.commit()
    conn.close()

    sync_user_playlists(db_path, "user1", "fake_token")

    conn = get_connection(db_path)

    playlists = conn.execute("SELECT * FROM playlists").fetchall()
    assert len(playlists) == 1
    assert playlists[0]["title"] == "Web Dev"

    videos = conn.execute("SELECT * FROM videos").fetchall()
    assert len(videos) == 2

    pv = conn.execute("SELECT * FROM playlist_videos").fetchall()
    assert len(pv) == 2

    embeddings = conn.execute("SELECT * FROM embeddings").fetchall()
    assert len(embeddings) == 2

    user = conn.execute("SELECT last_sync_at FROM users WHERE id = ?", ("user1",)).fetchone()
    assert user["last_sync_at"] is not None

    conn.close()
