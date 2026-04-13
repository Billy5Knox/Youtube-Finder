from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.auth import _sessions
from app.database import init_db, get_connection


client = TestClient(app)


def _setup_authenticated_user(db_path: str) -> dict:
    """Create a test user and session, return headers with session cookie."""
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO users (id, email, name, picture, access_token_encrypted) VALUES (?, ?, ?, ?, ?)",
        ("user1", "test@test.com", "Test User", "", b"fake_token"),
    )
    conn.commit()
    conn.close()

    _sessions["test-session"] = "user1"
    return {"Cookie": "session_id=test-session"}


def test_search_requires_auth():
    response = client.get("/api/search", params={"q": "test"})
    assert response.status_code == 401


@patch("app.routes.settings")
def test_search_returns_results(mock_settings, tmp_path):
    db_path = str(tmp_path / "test.db")
    mock_settings.DATABASE_PATH = db_path

    cookies = _setup_authenticated_user(db_path)

    # Insert test data
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO playlists (id, user_id, title) VALUES (?, ?, ?)",
        ("pl1", "user1", "Dev"),
    )
    conn.execute(
        "INSERT INTO videos (id, title, description, channel_name) VALUES (?, ?, ?, ?)",
        ("v1", "React Tutorial", "Learn React", "Fireship"),
    )
    conn.execute(
        "INSERT INTO videos_fts (video_id, title, description, channel_name) VALUES (?, ?, ?, ?)",
        ("v1", "React Tutorial", "Learn React", "Fireship"),
    )
    conn.execute(
        "INSERT INTO playlist_videos (playlist_id, video_id) VALUES (?, ?)",
        ("pl1", "v1"),
    )
    conn.commit()
    conn.close()

    response = client.get("/api/search", params={"q": "React"}, headers=cookies)
    assert response.status_code == 200

    data = response.json()
    assert data["query"] == "React"
    assert data["total"] >= 1
    assert data["results"][0]["video_id"] == "v1"
    assert "youtube.com" in data["results"][0]["youtube_url"]


@patch("app.routes.settings")
def test_get_playlists(mock_settings, tmp_path):
    db_path = str(tmp_path / "test.db")
    mock_settings.DATABASE_PATH = db_path

    cookies = _setup_authenticated_user(db_path)

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO playlists (id, user_id, title, description, thumbnail_url, item_count) VALUES (?, ?, ?, ?, ?, ?)",
        ("pl1", "user1", "Dev", "Dev stuff", "https://example.com/pl1.jpg", 5),
    )
    conn.commit()
    conn.close()

    response = client.get("/api/playlists", headers=cookies)
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Dev"
