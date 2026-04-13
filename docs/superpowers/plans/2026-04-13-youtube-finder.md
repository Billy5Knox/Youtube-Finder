# YouTube Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that syncs YouTube playlist data and provides keyword + semantic search across all saved videos.

**Architecture:** FastAPI backend with SQLite storage (FTS5 for keyword search, sentence-transformers for semantic search), React frontend via Vite. Google OAuth2 for YouTube API access. Backend serves the API, frontend is a standalone SPA.

**Tech Stack:** Python 3.11+, FastAPI, SQLite/FTS5, sentence-transformers, google-api-python-client, React 18, Vite

---

## File Structure

### Backend (`backend/`)

- `backend/requirements.txt` — Python dependencies
- `backend/app/__init__.py` — empty package init
- `backend/app/main.py` — FastAPI app creation, CORS, router mounting
- `backend/app/config.py` — settings (Google client ID/secret, DB path, secret key)
- `backend/app/database.py` — SQLite connection, table creation, FTS5 setup
- `backend/app/models.py` — Pydantic schemas for API request/response
- `backend/app/auth.py` — Google OAuth2 routes (login, callback, logout, current user)
- `backend/app/youtube.py` — YouTube Data API client (fetch playlists, fetch videos)
- `backend/app/sync.py` — Sync orchestration (initial + incremental sync, embedding generation)
- `backend/app/search.py` — Keyword search (FTS5) + semantic search + result merging
- `backend/app/embeddings.py` — sentence-transformers model loading and embedding generation
- `backend/app/routes.py` — API routes (search, playlists, sync, auth)

### Backend Tests (`backend/tests/`)

- `backend/tests/conftest.py` — shared fixtures (test DB, test client)
- `backend/tests/test_database.py` — database schema and FTS5 tests
- `backend/tests/test_search.py` — keyword search, semantic search, result merging
- `backend/tests/test_embeddings.py` — embedding generation tests
- `backend/tests/test_sync.py` — sync logic tests
- `backend/tests/test_youtube.py` — YouTube API client tests (mocked)
- `backend/tests/test_auth.py` — OAuth flow tests (mocked)
- `backend/tests/test_routes.py` — API endpoint integration tests

### Frontend (`frontend/`)

- `frontend/package.json` — dependencies and scripts
- `frontend/vite.config.js` — Vite config with API proxy
- `frontend/index.html` — HTML shell
- `frontend/src/main.jsx` — React entry point
- `frontend/src/App.jsx` — Root component, auth state, layout
- `frontend/src/App.css` — Global styles
- `frontend/src/components/TopBar.jsx` — Login/logout, avatar, sync button
- `frontend/src/components/SearchBar.jsx` — Search input with debounce
- `frontend/src/components/VideoCard.jsx` — Single video result card
- `frontend/src/components/ResultsGrid.jsx` — Grid of VideoCards
- `frontend/src/components/PlaylistFilter.jsx` — Playlist dropdown/toggle
- `frontend/src/hooks/useSearch.js` — Search API hook with debounce
- `frontend/src/hooks/useAuth.js` — Auth state hook
- `frontend/src/hooks/useSync.js` — Sync trigger and status hook
- `frontend/src/api.js` — API client (fetch wrappers for backend endpoints)

---

## Task 1: Project Scaffolding and Backend Dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create backend directory structure**

```bash
mkdir -p backend/app backend/tests
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
google-api-python-client==2.150.0
google-auth==2.35.0
google-auth-oauthlib==1.2.1
sentence-transformers==3.3.0
numpy==2.1.0
pydantic==2.9.0
cryptography==43.0.0
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
```

- [ ] **Step 3: Write config.py**

```python
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    DATABASE_PATH: str = os.environ.get("DATABASE_PATH", str(BASE_DIR / "youtube_finder.db"))
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production")
    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")

settings = Settings()
```

- [ ] **Step 4: Write app/__init__.py**

```python
```

(Empty file)

- [ ] **Step 5: Write main.py with FastAPI app skeleton**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="YouTube Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 6: Install dependencies and verify server starts**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Expected: Server starts on http://localhost:8000, `GET /health` returns `{"status": "ok"}`

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/config.py backend/app/main.py
git commit -m "feat: scaffold backend with FastAPI skeleton"
```

---

## Task 2: Database Schema and FTS5 Setup

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_database.py`

- [ ] **Step 1: Write the failing test for database schema creation**

```python
# backend/tests/test_database.py
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
```

- [ ] **Step 2: Write the conftest with shared fixtures**

```python
# backend/tests/conftest.py
import pytest
from app.database import init_db, get_connection


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def db_conn(db_path):
    conn = get_connection(db_path)
    yield conn
    conn.close()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_database.py -v
```

Expected: FAIL — `ModuleNotFoundError` or `ImportError` for `app.database`

- [ ] **Step 4: Write database.py with schema and FTS5**

```python
# backend/app/database.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_database.py -v
```

Expected: Both tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/database.py backend/tests/conftest.py backend/tests/test_database.py
git commit -m "feat: add SQLite schema with FTS5 full-text index"
```

---

## Task 3: Pydantic Models

**Files:**
- Create: `backend/app/models.py`

- [ ] **Step 1: Write models.py**

```python
# backend/app/models.py
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    picture: str
    last_sync_at: str | None


class PlaylistResponse(BaseModel):
    id: str
    title: str
    description: str
    thumbnail_url: str
    item_count: int


class VideoResult(BaseModel):
    video_id: str
    title: str
    description: str
    channel_name: str
    thumbnail_url: str
    published_at: str
    playlist_names: list[str]
    score: float
    youtube_url: str


class SearchResponse(BaseModel):
    results: list[VideoResult]
    query: str
    total: int


class SyncStatusResponse(BaseModel):
    is_syncing: bool
    last_sync_at: str | None
    playlists_synced: int
    videos_synced: int
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models.py
git commit -m "feat: add Pydantic request/response models"
```

---

## Task 4: Embedding Generation

**Files:**
- Create: `backend/app/embeddings.py`
- Create: `backend/tests/test_embeddings.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_embeddings.py
import numpy as np
from app.embeddings import EmbeddingService


def test_embed_single_text():
    service = EmbeddingService()
    vector = service.embed("How to build a REST API with FastAPI")

    assert isinstance(vector, np.ndarray)
    assert vector.shape == (384,)  # all-MiniLM-L6-v2 output dimension
    assert not np.all(vector == 0)


def test_embed_batch():
    service = EmbeddingService()
    texts = [
        "Python tutorial for beginners",
        "Advanced CSS grid layouts",
        "Machine learning with PyTorch",
    ]
    vectors = service.embed_batch(texts)

    assert len(vectors) == 3
    assert all(v.shape == (384,) for v in vectors)


def test_cosine_similarity():
    service = EmbeddingService()
    v1 = service.embed("Python programming tutorial")
    v2 = service.embed("Learn Python coding")
    v3 = service.embed("Chocolate cake recipe")

    sim_related = service.cosine_similarity(v1, v2)
    sim_unrelated = service.cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_embeddings.py -v
```

Expected: FAIL — `ImportError` for `app.embeddings`

- [ ] **Step 3: Write embeddings.py**

```python
# backend/app/embeddings.py
import numpy as np
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


class EmbeddingService:
    def __init__(self):
        self.model = _get_model()

    def embed(self, text: str) -> np.ndarray:
        return self.model.encode(text, normalize_embeddings=True)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [embeddings[i] for i in range(len(texts))]

    @staticmethod
    def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        return float(np.dot(v1, v2))

    @staticmethod
    def vector_to_bytes(vector: np.ndarray) -> bytes:
        return vector.tobytes()

    @staticmethod
    def bytes_to_vector(data: bytes) -> np.ndarray:
        return np.frombuffer(data, dtype=np.float32)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_embeddings.py -v
```

Expected: All 3 tests PASS (first run will download the model ~22MB)

- [ ] **Step 5: Commit**

```bash
git add backend/app/embeddings.py backend/tests/test_embeddings.py
git commit -m "feat: add embedding service with sentence-transformers"
```

---

## Task 5: Keyword Search (FTS5)

**Files:**
- Create: `backend/app/search.py`
- Create: `backend/tests/test_search.py`

- [ ] **Step 1: Write the failing test for keyword search**

```python
# backend/tests/test_search.py
from app.database import get_connection
from app.search import keyword_search, semantic_search, combined_search


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_search.py::test_keyword_search_finds_matching_videos -v
```

Expected: FAIL — `ImportError` for `app.search`

- [ ] **Step 3: Write keyword search in search.py**

```python
# backend/app/search.py
import numpy as np
from app.database import get_connection
from app.embeddings import EmbeddingService


def keyword_search(
    db_path: str,
    query: str,
    user_id: str,
    playlist_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conn = get_connection(db_path)

    fts_query = " OR ".join(query.split())

    sql = """
        SELECT
            v.id as video_id,
            v.title,
            v.description,
            v.channel_name,
            v.thumbnail_url,
            v.published_at,
            videos_fts.rank as score
        FROM videos_fts
        JOIN videos v ON v.id = videos_fts.video_id
        JOIN playlist_videos pv ON pv.video_id = v.id
        JOIN playlists p ON p.id = pv.playlist_id
        WHERE videos_fts MATCH ?
          AND p.user_id = ?
    """
    params: list = [fts_query, user_id]

    if playlist_id:
        sql += " AND pv.playlist_id = ?"
        params.append(playlist_id)

    sql += " GROUP BY v.id ORDER BY videos_fts.rank LIMIT ?"
    params.append(limit)

    cursor = conn.execute(sql, params)
    results = []
    for row in cursor.fetchall():
        results.append({
            "video_id": row["video_id"],
            "title": row["title"],
            "description": row["description"],
            "channel_name": row["channel_name"],
            "thumbnail_url": row["thumbnail_url"],
            "published_at": row["published_at"],
            "score": float(row["score"]),
        })

    conn.close()
    return results


def semantic_search(
    db_path: str,
    query: str,
    user_id: str,
    playlist_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    service = EmbeddingService()
    query_vector = service.embed(query)

    conn = get_connection(db_path)

    sql = """
        SELECT
            v.id as video_id,
            v.title,
            v.description,
            v.channel_name,
            v.thumbnail_url,
            v.published_at,
            e.vector
        FROM embeddings e
        JOIN videos v ON v.id = e.video_id
        JOIN playlist_videos pv ON pv.video_id = v.id
        JOIN playlists p ON p.id = pv.playlist_id
        WHERE p.user_id = ?
    """
    params: list = [user_id]

    if playlist_id:
        sql += " AND pv.playlist_id = ?"
        params.append(playlist_id)

    sql += " GROUP BY v.id"

    cursor = conn.execute(sql, params)
    scored_results = []
    for row in cursor.fetchall():
        stored_vector = EmbeddingService.bytes_to_vector(row["vector"])
        score = EmbeddingService.cosine_similarity(query_vector, stored_vector)
        scored_results.append({
            "video_id": row["video_id"],
            "title": row["title"],
            "description": row["description"],
            "channel_name": row["channel_name"],
            "thumbnail_url": row["thumbnail_url"],
            "published_at": row["published_at"],
            "score": score,
        })

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    conn.close()
    return scored_results[:limit]


def combined_search(
    db_path: str,
    query: str,
    user_id: str,
    playlist_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    kw_results = keyword_search(db_path, query, user_id, playlist_id, limit)
    sem_results = semantic_search(db_path, query, user_id, playlist_id, limit)

    # Merge: keyword results weighted 2x
    merged: dict[str, dict] = {}

    for r in kw_results:
        vid = r["video_id"]
        r["score"] = abs(r["score"]) * 2.0  # FTS5 rank is negative, higher abs = better
        merged[vid] = r

    for r in sem_results:
        vid = r["video_id"]
        if vid in merged:
            merged[vid]["score"] = max(merged[vid]["score"], r["score"])
        else:
            merged[vid] = r

    results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return results[:limit]
```

- [ ] **Step 4: Run keyword search tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_search.py -v -k "keyword"
```

Expected: All 4 keyword tests PASS

- [ ] **Step 5: Add semantic and combined search tests**

Add to `backend/tests/test_search.py`:

```python
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
```

Add this import at the top of the file:

```python
from app.embeddings import EmbeddingService
```

- [ ] **Step 6: Run all search tests**

```bash
cd backend
python -m pytest tests/test_search.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/search.py backend/tests/test_search.py
git commit -m "feat: add keyword, semantic, and combined search"
```

---

## Task 6: Google OAuth2 Authentication

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth.py
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


client = TestClient(app)


def test_login_redirects_to_google():
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]


def test_me_returns_401_when_not_logged_in():
    response = client.get("/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_auth.py -v
```

Expected: FAIL — 404 because routes don't exist yet

- [ ] **Step 3: Write auth.py**

```python
# backend/app/auth.py
import json
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import get_connection, init_db

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory session store (simple approach for single-user app)
_sessions: dict[str, str] = {}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
YOUTUBE_SCOPES = "openid email profile https://www.googleapis.com/auth/youtube.readonly"


def get_current_user_id(request: Request) -> str | None:
    session_id = request.cookies.get("session_id")
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    return None


def require_user(request: Request) -> str:
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/login")
def login():
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/callback")
async def callback(code: str, request: Request):
    import httpx

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        tokens = token_response.json()

        # Get user info
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo = userinfo_response.json()

    # Store user in database
    init_db(settings.DATABASE_PATH)
    conn = get_connection(settings.DATABASE_PATH)
    conn.execute(
        """INSERT INTO users (id, email, name, picture, access_token_encrypted, refresh_token_encrypted)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             email=excluded.email,
             name=excluded.name,
             picture=excluded.picture,
             access_token_encrypted=excluded.access_token_encrypted,
             refresh_token_encrypted=excluded.refresh_token_encrypted""",
        (
            userinfo["id"],
            userinfo.get("email", ""),
            userinfo.get("name", ""),
            userinfo.get("picture", ""),
            tokens["access_token"].encode(),  # TODO: encrypt in production
            tokens.get("refresh_token", "").encode(),
        ),
    )
    conn.commit()
    conn.close()

    # Create session
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = userinfo["id"]

    response = RedirectResponse(url=settings.FRONTEND_URL)
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


@router.get("/me")
def me(request: Request):
    user_id = require_user(request)
    conn = get_connection(settings.DATABASE_PATH)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "picture": row["picture"],
        "last_sync_at": row["last_sync_at"],
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    response = RedirectResponse(url=settings.FRONTEND_URL)
    response.delete_cookie("session_id")
    return response
```

- [ ] **Step 4: Mount auth router in main.py**

Update `backend/app/main.py` — add after CORS middleware:

```python
from app.auth import router as auth_router

app.include_router(auth_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_auth.py -v
```

Expected: Both tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth.py backend/tests/test_auth.py backend/app/main.py
git commit -m "feat: add Google OAuth2 authentication"
```

---

## Task 7: YouTube API Client

**Files:**
- Create: `backend/app/youtube.py`
- Create: `backend/tests/test_youtube.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_youtube.py
from unittest.mock import MagicMock, patch
from app.youtube import fetch_playlists, fetch_playlist_videos


def _mock_playlists_response():
    return {
        "items": [
            {
                "id": "PLabc123",
                "snippet": {
                    "title": "Web Dev",
                    "description": "Web development tutorials",
                    "thumbnails": {"medium": {"url": "https://example.com/thumb1.jpg"}},
                },
                "contentDetails": {"itemCount": 5},
                "etag": "etag123",
            },
            {
                "id": "PLdef456",
                "snippet": {
                    "title": "Python",
                    "description": "Python tutorials",
                    "thumbnails": {"medium": {"url": "https://example.com/thumb2.jpg"}},
                },
                "contentDetails": {"itemCount": 3},
                "etag": "etag456",
            },
        ],
        "nextPageToken": None,
    }


def _mock_playlist_items_response():
    return {
        "items": [
            {
                "snippet": {
                    "resourceId": {"videoId": "vid001"},
                    "title": "React Hooks Tutorial",
                    "description": "Learn React hooks",
                    "videoOwnerChannelTitle": "Fireship",
                    "thumbnails": {"medium": {"url": "https://example.com/vid1.jpg"}},
                    "publishedAt": "2024-01-15T00:00:00Z",
                    "position": 0,
                },
                "contentDetails": {"videoPublishedAt": "2024-01-10T00:00:00Z"},
            },
        ],
        "nextPageToken": None,
    }


@patch("app.youtube._build_youtube_service")
def test_fetch_playlists(mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    mock_service.playlists().list().execute.return_value = _mock_playlists_response()

    playlists = fetch_playlists("fake_token")

    assert len(playlists) == 2
    assert playlists[0]["id"] == "PLabc123"
    assert playlists[0]["title"] == "Web Dev"
    assert playlists[1]["id"] == "PLdef456"


@patch("app.youtube._build_youtube_service")
def test_fetch_playlist_videos(mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    mock_service.playlistItems().list().execute.return_value = _mock_playlist_items_response()

    videos = fetch_playlist_videos("fake_token", "PLabc123")

    assert len(videos) == 1
    assert videos[0]["video_id"] == "vid001"
    assert videos[0]["title"] == "React Hooks Tutorial"
    assert videos[0]["channel_name"] == "Fireship"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_youtube.py -v
```

Expected: FAIL — `ImportError` for `app.youtube`

- [ ] **Step 3: Write youtube.py**

```python
# backend/app/youtube.py
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


def _build_youtube_service(access_token: str):
    credentials = Credentials(token=access_token)
    return build("youtube", "v3", credentials=credentials)


def fetch_playlists(access_token: str) -> list[dict]:
    service = _build_youtube_service(access_token)
    playlists = []
    page_token = None

    while True:
        response = service.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=50,
            pageToken=page_token,
        ).execute()

        for item in response.get("items", []):
            thumbnails = item["snippet"].get("thumbnails", {})
            thumb_url = thumbnails.get("medium", {}).get("url", "")

            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", ""),
                "thumbnail_url": thumb_url,
                "item_count": item["contentDetails"]["itemCount"],
                "etag": item.get("etag", ""),
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return playlists


def fetch_playlist_videos(access_token: str, playlist_id: str) -> list[dict]:
    service = _build_youtube_service(access_token)
    videos = []
    page_token = None

    while True:
        response = service.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            video_id = snippet["resourceId"].get("videoId")
            if not video_id:
                continue

            thumbnails = snippet.get("thumbnails", {})
            thumb_url = thumbnails.get("medium", {}).get("url", "")

            videos.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_name": snippet.get("videoOwnerChannelTitle", ""),
                "thumbnail_url": thumb_url,
                "published_at": item["contentDetails"].get("videoPublishedAt", ""),
                "position": snippet.get("position", 0),
                "added_at": snippet.get("publishedAt", ""),
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return videos
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_youtube.py -v
```

Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/youtube.py backend/tests/test_youtube.py
git commit -m "feat: add YouTube Data API client"
```

---

## Task 8: Sync Orchestration

**Files:**
- Create: `backend/app/sync.py`
- Create: `backend/tests/test_sync.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sync.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_sync.py -v
```

Expected: FAIL — `ImportError` for `app.sync`

- [ ] **Step 3: Write sync.py**

```python
# backend/app/sync.py
from datetime import datetime, timezone

from app.database import get_connection
from app.youtube import fetch_playlists, fetch_playlist_videos
from app.embeddings import EmbeddingService


def sync_user_playlists(db_path: str, user_id: str, access_token: str) -> dict:
    playlists = fetch_playlists(access_token)
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
        videos = fetch_playlist_videos(access_token, pl["id"])

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_sync.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/sync.py backend/tests/test_sync.py
git commit -m "feat: add playlist sync orchestration with incremental updates"
```

---

## Task 9: API Routes

**Files:**
- Create: `backend/app/routes.py`
- Create: `backend/tests/test_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routes.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_routes.py::test_search_requires_auth -v
```

Expected: FAIL — 404 because `/api/search` doesn't exist

- [ ] **Step 3: Write routes.py**

```python
# backend/app/routes.py
from fastapi import APIRouter, Request, HTTPException

from app.auth import require_user
from app.config import settings
from app.database import get_connection
from app.search import keyword_search, combined_search
from app.sync import sync_user_playlists

router = APIRouter(prefix="/api", tags=["api"])


def _get_playlist_names(db_path: str, video_id: str, user_id: str) -> list[str]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT p.title FROM playlists p
           JOIN playlist_videos pv ON pv.playlist_id = p.id
           WHERE pv.video_id = ? AND p.user_id = ?""",
        (video_id, user_id),
    ).fetchall()
    conn.close()
    return [row["title"] for row in rows]


@router.get("/search")
def search(request: Request, q: str, playlist_id: str | None = None, mode: str = "combined"):
    user_id = require_user(request)

    if not q.strip():
        return {"results": [], "query": q, "total": 0}

    if mode == "keyword":
        raw_results = keyword_search(settings.DATABASE_PATH, q, user_id, playlist_id)
    else:
        try:
            raw_results = combined_search(settings.DATABASE_PATH, q, user_id, playlist_id)
        except Exception:
            # Fall back to keyword search if embeddings aren't available
            raw_results = keyword_search(settings.DATABASE_PATH, q, user_id, playlist_id)

    results = []
    for r in raw_results:
        results.append({
            "video_id": r["video_id"],
            "title": r["title"],
            "description": r["description"],
            "channel_name": r["channel_name"],
            "thumbnail_url": r["thumbnail_url"],
            "published_at": r["published_at"],
            "playlist_names": _get_playlist_names(settings.DATABASE_PATH, r["video_id"], user_id),
            "score": r["score"],
            "youtube_url": f"https://www.youtube.com/watch?v={r['video_id']}",
        })

    return {"results": results, "query": q, "total": len(results)}


@router.get("/playlists")
def get_playlists(request: Request):
    user_id = require_user(request)
    conn = get_connection(settings.DATABASE_PATH)

    rows = conn.execute(
        "SELECT id, title, description, thumbnail_url, item_count FROM playlists WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "thumbnail_url": row["thumbnail_url"],
            "item_count": row["item_count"],
        }
        for row in rows
    ]


@router.post("/sync")
def trigger_sync(request: Request):
    user_id = require_user(request)
    conn = get_connection(settings.DATABASE_PATH)
    user = conn.execute(
        "SELECT access_token_encrypted FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if not user or not user["access_token_encrypted"]:
        raise HTTPException(status_code=400, detail="No access token found. Please re-login.")

    access_token = user["access_token_encrypted"].decode()
    result = sync_user_playlists(settings.DATABASE_PATH, user_id, access_token)

    return {
        "is_syncing": False,
        "last_sync_at": _get_last_sync(user_id),
        "playlists_synced": result["playlists_synced"],
        "videos_synced": result["videos_synced"],
    }


def _get_last_sync(user_id: str) -> str | None:
    conn = get_connection(settings.DATABASE_PATH)
    row = conn.execute("SELECT last_sync_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row["last_sync_at"] if row else None
```

- [ ] **Step 4: Mount API router in main.py**

Update `backend/app/main.py` — add:

```python
from app.routes import router as api_router
from app.database import init_db
from app.config import settings

# Initialize database on startup
@app.on_event("startup")
def startup():
    init_db(settings.DATABASE_PATH)

app.include_router(api_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_routes.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes.py backend/tests/test_routes.py backend/app/main.py
git commit -m "feat: add API routes for search, playlists, and sync"
```

---

## Task 10: Frontend Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/App.css`
- Create: `frontend/src/api.js`

- [ ] **Step 1: Scaffold Vite + React project**

```bash
cd D:/AI/Youtube-Finder
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

- [ ] **Step 2: Configure Vite API proxy**

Replace `frontend/vite.config.js`:

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
```

- [ ] **Step 3: Write API client**

```javascript
// frontend/src/api.js
const API_BASE = "";

export async function fetchCurrentUser() {
  const res = await fetch(`${API_BASE}/auth/me`, { credentials: "include" });
  if (!res.ok) return null;
  return res.json();
}

export async function searchVideos(query, playlistId = null) {
  const params = new URLSearchParams({ q: query });
  if (playlistId) params.set("playlist_id", playlistId);
  const res = await fetch(`${API_BASE}/api/search?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

export async function fetchPlaylists() {
  const res = await fetch(`${API_BASE}/api/playlists`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch playlists");
  return res.json();
}

export async function triggerSync() {
  const res = await fetch(`${API_BASE}/api/sync`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Sync failed");
  return res.json();
}
```

- [ ] **Step 4: Write root App component**

```jsx
// frontend/src/App.jsx
import { useState, useEffect } from "react";
import { fetchCurrentUser } from "./api";
import TopBar from "./components/TopBar";
import SearchBar from "./components/SearchBar";
import ResultsGrid from "./components/ResultsGrid";
import PlaylistFilter from "./components/PlaylistFilter";
import "./App.css";

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("");
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (!user) {
    return (
      <div className="login-page">
        <h1>YouTube Finder</h1>
        <p>Search across all your YouTube playlists.</p>
        <a href="/auth/login" className="login-button">
          Sign in with Google
        </a>
      </div>
    );
  }

  return (
    <div className="app">
      <TopBar user={user} />
      <main className="main-content">
        <SearchBar
          query={query}
          setQuery={setQuery}
          setResults={setResults}
          selectedPlaylist={selectedPlaylist}
        />
        <PlaylistFilter
          selectedPlaylist={selectedPlaylist}
          setSelectedPlaylist={setSelectedPlaylist}
        />
        <ResultsGrid results={results} query={query} />
      </main>
    </div>
  );
}

export default App;
```

- [ ] **Step 5: Write App.css**

```css
/* frontend/src/App.css */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #0f0f0f;
  color: #f1f1f1;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  font-size: 1.2rem;
  color: #aaa;
}

.login-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 1rem;
}

.login-page h1 {
  font-size: 2.5rem;
}

.login-page p {
  color: #aaa;
  font-size: 1.1rem;
}

.login-button {
  display: inline-block;
  padding: 0.75rem 2rem;
  background: #ff0000;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 500;
  margin-top: 1rem;
}

.login-button:hover {
  background: #cc0000;
}

.app {
  min-height: 100vh;
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
```

- [ ] **Step 6: Verify frontend starts**

```bash
cd frontend
npm run dev
```

Expected: Vite dev server starts on http://localhost:5173, shows the login page

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React frontend with Vite, API client, and root layout"
```

---

## Task 11: Frontend Components — TopBar

**Files:**
- Create: `frontend/src/components/TopBar.jsx`

- [ ] **Step 1: Write TopBar component**

```jsx
// frontend/src/components/TopBar.jsx
import { useState } from "react";
import { triggerSync } from "../api";

function TopBar({ user }) {
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState(user.last_sync_at);

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await triggerSync();
      setLastSync(result.last_sync_at);
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncing(false);
    }
  }

  function formatSyncTime(isoString) {
    if (!isoString) return "Never";
    return new Date(isoString).toLocaleString();
  }

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <h1 className="logo">YouTube Finder</h1>
      </div>
      <div className="top-bar-right">
        <span className="sync-status">
          Last synced: {formatSyncTime(lastSync)}
        </span>
        <button
          className="sync-button"
          onClick={handleSync}
          disabled={syncing}
        >
          {syncing ? "Syncing..." : "Sync Now"}
        </button>
        <div className="user-info">
          {user.picture && (
            <img src={user.picture} alt="" className="avatar" />
          )}
          <span className="user-name">{user.name}</span>
        </div>
        <a href="/auth/logout" className="logout-link">Logout</a>
      </div>
    </header>
  );
}

export default TopBar;
```

- [ ] **Step 2: Add TopBar styles to App.css**

Append to `frontend/src/App.css`:

```css
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: #181818;
  border-bottom: 1px solid #333;
}

.logo {
  font-size: 1.3rem;
  color: #ff0000;
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.sync-status {
  font-size: 0.8rem;
  color: #888;
}

.sync-button {
  padding: 0.4rem 1rem;
  background: #333;
  color: #f1f1f1;
  border: 1px solid #555;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}

.sync-button:hover:not(:disabled) {
  background: #444;
}

.sync-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
}

.user-name {
  font-size: 0.9rem;
}

.logout-link {
  color: #aaa;
  font-size: 0.85rem;
  text-decoration: none;
}

.logout-link:hover {
  color: #f1f1f1;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TopBar.jsx frontend/src/App.css
git commit -m "feat: add TopBar component with sync button and user info"
```

---

## Task 12: Frontend Components — SearchBar with Debounce

**Files:**
- Create: `frontend/src/hooks/useSearch.js`
- Create: `frontend/src/components/SearchBar.jsx`

- [ ] **Step 1: Write useSearch hook**

```javascript
// frontend/src/hooks/useSearch.js
import { useEffect, useRef } from "react";
import { searchVideos } from "../api";

export function useSearch(query, selectedPlaylist, setResults) {
  const timerRef = useRef(null);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    if (!query.trim()) {
      setResults([]);
      return;
    }

    timerRef.current = setTimeout(async () => {
      try {
        const data = await searchVideos(query, selectedPlaylist);
        setResults(data.results);
      } catch (err) {
        console.error("Search error:", err);
      }
    }, 300);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [query, selectedPlaylist, setResults]);
}
```

- [ ] **Step 2: Write SearchBar component**

```jsx
// frontend/src/components/SearchBar.jsx
import { useSearch } from "../hooks/useSearch";

function SearchBar({ query, setQuery, setResults, selectedPlaylist }) {
  useSearch(query, selectedPlaylist, setResults);

  return (
    <div className="search-bar">
      <input
        type="text"
        className="search-input"
        placeholder="Search your saved videos..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoFocus
      />
    </div>
  );
}

export default SearchBar;
```

- [ ] **Step 3: Add SearchBar styles to App.css**

Append to `frontend/src/App.css`:

```css
.search-bar {
  margin-bottom: 1.5rem;
}

.search-input {
  width: 100%;
  padding: 1rem 1.25rem;
  font-size: 1.1rem;
  background: #181818;
  color: #f1f1f1;
  border: 2px solid #333;
  border-radius: 8px;
  outline: none;
}

.search-input:focus {
  border-color: #555;
}

.search-input::placeholder {
  color: #666;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useSearch.js frontend/src/components/SearchBar.jsx frontend/src/App.css
git commit -m "feat: add SearchBar with 300ms debounced search"
```

---

## Task 13: Frontend Components — VideoCard and ResultsGrid

**Files:**
- Create: `frontend/src/components/VideoCard.jsx`
- Create: `frontend/src/components/ResultsGrid.jsx`

- [ ] **Step 1: Write VideoCard component**

```jsx
// frontend/src/components/VideoCard.jsx
function VideoCard({ video }) {
  return (
    <a
      href={video.youtube_url}
      target="_blank"
      rel="noopener noreferrer"
      className="video-card"
    >
      <div className="video-thumbnail">
        {video.thumbnail_url ? (
          <img src={video.thumbnail_url} alt={video.title} />
        ) : (
          <div className="thumbnail-placeholder" />
        )}
      </div>
      <div className="video-info">
        <h3 className="video-title">{video.title}</h3>
        <p className="video-channel">{video.channel_name}</p>
        <div className="video-playlists">
          {video.playlist_names.map((name) => (
            <span key={name} className="playlist-tag">
              {name}
            </span>
          ))}
        </div>
      </div>
    </a>
  );
}

export default VideoCard;
```

- [ ] **Step 2: Write ResultsGrid component**

```jsx
// frontend/src/components/ResultsGrid.jsx
import VideoCard from "./VideoCard";

function ResultsGrid({ results, query }) {
  if (!query.trim()) {
    return (
      <div className="empty-state">
        <p>Start typing to search your saved videos.</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="empty-state">
        <p>No videos found for "{query}".</p>
      </div>
    );
  }

  return (
    <div className="results-grid">
      {results.map((video) => (
        <VideoCard key={video.video_id} video={video} />
      ))}
    </div>
  );
}

export default ResultsGrid;
```

- [ ] **Step 3: Add card and grid styles to App.css**

Append to `frontend/src/App.css`:

```css
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.25rem;
}

.video-card {
  display: flex;
  flex-direction: column;
  background: #181818;
  border-radius: 8px;
  overflow: hidden;
  text-decoration: none;
  color: inherit;
  transition: background 0.2s;
}

.video-card:hover {
  background: #222;
}

.video-thumbnail img {
  width: 100%;
  aspect-ratio: 16/9;
  object-fit: cover;
  display: block;
}

.thumbnail-placeholder {
  width: 100%;
  aspect-ratio: 16/9;
  background: #333;
}

.video-info {
  padding: 0.75rem;
}

.video-title {
  font-size: 0.95rem;
  font-weight: 500;
  line-height: 1.3;
  margin-bottom: 0.3rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.video-channel {
  font-size: 0.8rem;
  color: #aaa;
  margin-bottom: 0.5rem;
}

.video-playlists {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.playlist-tag {
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  background: #333;
  border-radius: 3px;
  color: #ccc;
}

.empty-state {
  text-align: center;
  padding: 4rem 1rem;
  color: #666;
  font-size: 1.1rem;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/VideoCard.jsx frontend/src/components/ResultsGrid.jsx frontend/src/App.css
git commit -m "feat: add VideoCard and ResultsGrid components"
```

---

## Task 14: Frontend Components — Playlist Filter

**Files:**
- Create: `frontend/src/components/PlaylistFilter.jsx`

- [ ] **Step 1: Write PlaylistFilter component**

```jsx
// frontend/src/components/PlaylistFilter.jsx
import { useState, useEffect } from "react";
import { fetchPlaylists } from "../api";

function PlaylistFilter({ selectedPlaylist, setSelectedPlaylist }) {
  const [playlists, setPlaylists] = useState([]);

  useEffect(() => {
    fetchPlaylists()
      .then(setPlaylists)
      .catch((err) => console.error("Failed to load playlists:", err));
  }, []);

  if (playlists.length === 0) return null;

  return (
    <div className="playlist-filter">
      <button
        className={`filter-chip ${selectedPlaylist === null ? "active" : ""}`}
        onClick={() => setSelectedPlaylist(null)}
      >
        All Playlists
      </button>
      {playlists.map((pl) => (
        <button
          key={pl.id}
          className={`filter-chip ${selectedPlaylist === pl.id ? "active" : ""}`}
          onClick={() =>
            setSelectedPlaylist(selectedPlaylist === pl.id ? null : pl.id)
          }
        >
          {pl.title} ({pl.item_count})
        </button>
      ))}
    </div>
  );
}

export default PlaylistFilter;
```

- [ ] **Step 2: Add filter styles to App.css**

Append to `frontend/src/App.css`:

```css
.playlist-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.filter-chip {
  padding: 0.35rem 0.85rem;
  font-size: 0.85rem;
  background: #222;
  color: #aaa;
  border: 1px solid #333;
  border-radius: 20px;
  cursor: pointer;
}

.filter-chip:hover {
  background: #333;
  color: #f1f1f1;
}

.filter-chip.active {
  background: #ff0000;
  color: white;
  border-color: #ff0000;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PlaylistFilter.jsx frontend/src/App.css
git commit -m "feat: add playlist filter chips"
```

---

## Task 15: Initialize Git and Final Integration

**Files:**
- Create: `.gitignore`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Initialize git repository**

```bash
cd D:/AI/Youtube-Finder
git init
```

- [ ] **Step 2: Create .gitignore**

```
# Python
__pycache__/
*.pyc
*.egg-info/
.venv/
venv/
*.db

# Node
node_modules/
dist/

# Environment
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# ML models
sentence-transformers/
```

- [ ] **Step 3: Update CLAUDE.md**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

YouTube Finder — a web app that syncs YouTube playlist data and provides keyword + semantic search across all saved videos. FastAPI backend with React frontend.

## Build & Run

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload  # runs on :8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # runs on :5173, proxies API to :8000
```

### Environment Variables
Required in `backend/.env` or exported:
- `GOOGLE_CLIENT_ID` — Google OAuth2 client ID
- `GOOGLE_CLIENT_SECRET` — Google OAuth2 client secret
- `SECRET_KEY` — session signing key (any random string)

### Tests
```bash
cd backend
python -m pytest tests/ -v              # all tests
python -m pytest tests/test_search.py -v  # single file
python -m pytest tests/test_search.py::test_keyword_search_finds_matching_videos -v  # single test
```

## Architecture

- `backend/app/` — FastAPI application
  - `auth.py` — Google OAuth2 login/logout, session management
  - `youtube.py` — YouTube Data API v3 client (fetch playlists + videos)
  - `sync.py` — Sync orchestration (initial + incremental), embedding generation
  - `search.py` — FTS5 keyword search + sentence-transformer semantic search + result merging
  - `embeddings.py` — Local sentence-transformers model (`all-MiniLM-L6-v2`), vector operations
  - `database.py` — SQLite schema, FTS5 virtual table, connection management
  - `routes.py` — API endpoints: `/api/search`, `/api/playlists`, `/api/sync`
- `frontend/src/` — React SPA (Vite)
  - Components: TopBar, SearchBar, VideoCard, ResultsGrid, PlaylistFilter
  - Hooks: useSearch (debounced), useAuth, useSync
  - `api.js` — fetch wrappers for backend endpoints

Search runs keyword (FTS5) and semantic (cosine similarity on embeddings) in parallel, merges results with keyword matches weighted higher.
```

- [ ] **Step 4: Create initial commit**

```bash
git add .gitignore CLAUDE.md docs/
git commit -m "feat: initialize project with design spec, plan, and CLAUDE.md"
```

- [ ] **Step 5: Verify full backend test suite passes**

```bash
cd backend
python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 6: Verify frontend dev server starts**

```bash
cd frontend
npm run dev
```

Expected: Vite dev server starts without errors
