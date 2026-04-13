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
python -m pytest tests/ -v                                                      # all tests
python -m pytest tests/test_search.py -v                                        # single file
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
  - Hooks: useSearch (debounced)
  - `api.js` — fetch wrappers for backend endpoints

Search runs keyword (FTS5) and semantic (cosine similarity on embeddings) in parallel, merges results with keyword matches weighted higher.
