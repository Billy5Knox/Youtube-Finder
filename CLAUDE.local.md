# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

YouTube Finder — a web app that syncs YouTube playlist data and provides keyword + semantic search across all saved videos. FastAPI backend with React frontend.

## Build & Run

### Quick Start (Windows)
```bash
start.bat   # starts backend + frontend, opens browser
```

### Manual Start
```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload  # runs on :8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev  # runs on :5173, proxies /api and /auth to :8000
```

### Environment Variables
Stored in `backend/.env` (auto-loaded via python-dotenv):
- `GOOGLE_CLIENT_ID` — Google OAuth2 client ID
- `GOOGLE_CLIENT_SECRET` — Google OAuth2 client secret
- `SECRET_KEY` — session signing key

### Tests
```bash
cd backend
python -m pytest tests/ -v                                                      # all tests
python -m pytest tests/test_search.py -v                                        # single file
python -m pytest tests/test_search.py::test_keyword_search_finds_matching_videos -v  # single test
```

### Frontend Build
```bash
cd frontend
npm run build  # production build to dist/
```

## Architecture

- `backend/app/` — FastAPI application
  - `main.py` — App creation, CORS, router mounting, startup DB init
  - `config.py` — Settings from env vars / `.env` file via python-dotenv
  - `auth.py` — Google OAuth2 login/callback/logout/me, in-memory session store
  - `youtube.py` — YouTube Data API v3 client (fetch playlists + videos, paginated)
  - `sync.py` — Sync orchestration (initial + incremental via etag/item_count), embedding generation
  - `search.py` — FTS5 keyword search + sentence-transformer semantic search + result merging
  - `embeddings.py` — Local sentence-transformers model (`all-MiniLM-L6-v2`), singleton pattern
  - `database.py` — SQLite schema, FTS5 virtual table (`video_id UNINDEXED`), connection management
  - `routes.py` — API endpoints: `GET /api/search`, `GET /api/playlists`, `POST /api/sync`
  - `models.py` — Pydantic response schemas
- `frontend/src/` — React SPA (Vite)
  - `App.jsx` — Root component with auth state, login page, main layout
  - `api.js` — Fetch wrappers for all backend endpoints
  - `components/` — TopBar, SearchBar, VideoCard, ResultsGrid, PlaylistFilter
  - `hooks/useSearch.js` — Debounced search hook (300ms)

## Key Design Decisions

- Search runs keyword (FTS5) and semantic (cosine similarity) in parallel, merges results with keyword matches weighted 2x higher
- FTS5 uses `video_id UNINDEXED` — stored for retrieval but not tokenized for search
- Embeddings use `all-MiniLM-L6-v2` (384-dim, 22MB) with normalized vectors, so cosine similarity = dot product
- Incremental sync skips playlists whose etag and item_count haven't changed
- Combined search falls back to keyword-only if embeddings aren't available
- In-memory session store (`_sessions` dict in auth.py) — appropriate for single-user app
