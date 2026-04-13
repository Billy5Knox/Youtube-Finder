from app.database import get_connection
from app.search import keyword_search, semantic_search, combined_search
from app.embeddings import EmbeddingService


def _insert_test_videos(db_path: str):
    conn = get_connection(db_path)

    conn.execute(
        "INSERT INTO users (id, email, name, picture) VALUES (?, ?, ?, ?)",
        ("user1", "test@test.com", "Test User", ""),
    )
    conn.execute(
        "INSERT INTO playlists (id, user_id, title) VALUES (?, ?, ?)",
        ("pl1", "user1", "Web Dev"),
    )
    conn.execute(
        "INSERT INTO playlists (id, user_id, title) VALUES (?, ?, ?)",
        ("pl2", "user1", "Python"),
    )

    videos = [
        ("v1", "React Hooks Tutorial", "Learn useState and useEffect in React", "Fireship"),
        ("v2", "Advanced CSS Grid Layout", "Master CSS grid for responsive design", "Kevin Powell"),
        ("v3", "FastAPI Python REST API", "Build APIs with FastAPI and Python", "TechWithTim"),
        ("v4", "Chocolate Cake Recipe", "Best chocolate cake ever", "Binging with Babish"),
    ]
    for vid, title, desc, channel in videos:
        conn.execute(
            "INSERT INTO videos (id, title, description, channel_name) VALUES (?, ?, ?, ?)",
            (vid, title, desc, channel),
        )
        conn.execute(
            "INSERT INTO videos_fts (video_id, title, description, channel_name) VALUES (?, ?, ?, ?)",
            (vid, title, desc, channel),
        )

    conn.execute(
        "INSERT INTO playlist_videos (playlist_id, video_id) VALUES (?, ?)",
        ("pl1", "v1"),
    )
    conn.execute(
        "INSERT INTO playlist_videos (playlist_id, video_id) VALUES (?, ?)",
        ("pl1", "v2"),
    )
    conn.execute(
        "INSERT INTO playlist_videos (playlist_id, video_id) VALUES (?, ?)",
        ("pl2", "v3"),
    )
    conn.execute(
        "INSERT INTO playlist_videos (playlist_id, video_id) VALUES (?, ?)",
        ("pl2", "v4"),
    )

    conn.commit()
    conn.close()


def test_keyword_search_finds_matching_videos(db_path):
    _insert_test_videos(db_path)
    results = keyword_search(db_path, "React", user_id="user1")

    assert len(results) == 1
    assert results[0]["video_id"] == "v1"
    assert results[0]["title"] == "React Hooks Tutorial"


def test_keyword_search_matches_channel_name(db_path):
    _insert_test_videos(db_path)
    results = keyword_search(db_path, "Kevin Powell", user_id="user1")

    assert len(results) == 1
    assert results[0]["video_id"] == "v2"


def test_keyword_search_no_results(db_path):
    _insert_test_videos(db_path)
    results = keyword_search(db_path, "quantum physics", user_id="user1")

    assert len(results) == 0


def test_keyword_search_filter_by_playlist(db_path):
    _insert_test_videos(db_path)
    results = keyword_search(db_path, "Python", user_id="user1", playlist_id="pl2")

    assert len(results) == 1
    assert results[0]["video_id"] == "v3"


def test_semantic_search_finds_related_videos(db_path):
    _insert_test_videos(db_path)

    # Add embeddings for test videos
    service = EmbeddingService()
    conn = get_connection(db_path)
    for vid_id in ["v1", "v2", "v3", "v4"]:
        row = conn.execute("SELECT title, description FROM videos WHERE id = ?", (vid_id,)).fetchone()
        text = f"{row['title']} {row['description']}"
        vector = service.embed(text)
        conn.execute(
            "INSERT INTO embeddings (video_id, vector) VALUES (?, ?)",
            (vid_id, service.vector_to_bytes(vector)),
        )
    conn.commit()
    conn.close()

    results = semantic_search(db_path, "web development frontend", user_id="user1")

    # React and CSS videos should rank higher than cake recipe
    video_ids = [r["video_id"] for r in results]
    cake_index = video_ids.index("v4")
    react_index = video_ids.index("v1")
    assert react_index < cake_index


def test_combined_search_merges_results(db_path):
    _insert_test_videos(db_path)

    service = EmbeddingService()
    conn = get_connection(db_path)
    for vid_id in ["v1", "v2", "v3", "v4"]:
        row = conn.execute("SELECT title, description FROM videos WHERE id = ?", (vid_id,)).fetchone()
        text = f"{row['title']} {row['description']}"
        vector = service.embed(text)
        conn.execute(
            "INSERT INTO embeddings (video_id, vector) VALUES (?, ?)",
            (vid_id, service.vector_to_bytes(vector)),
        )
    conn.commit()
    conn.close()

    results = combined_search(db_path, "React", user_id="user1")

    assert len(results) > 0
    # React video should be first (exact keyword match + semantic relevance)
    assert results[0]["video_id"] == "v1"
