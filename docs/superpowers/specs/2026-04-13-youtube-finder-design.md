# YouTube Finder — Design Spec

## Problem

YouTube's built-in search doesn't filter to saved/playlist videos. Finding a previously saved video requires manually opening each playlist and scrolling through. There's no way to search across all playlists at once, and no semantic understanding of video content beyond exact title matches.

## Target User

A single user with hundreds of saved YouTube videos across 10-20 playlists who remembers videos primarily by topic/title keywords.

## Solution

A web app (FastAPI + React) that syncs YouTube playlist data via the YouTube Data API, stores it locally in SQLite, and provides both keyword and AI-powered semantic search across all playlists.

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────┐
│  React Frontend │────▶│  FastAPI Backend              │
│  (Vite + React) │◀────│                               │
│                 │     │  ├─ YouTube API integration    │
│  - Search bar   │     │  ├─ Keyword search (SQLite    │
│  - Results list │     │  │   FTS5 full-text search)   │
│  - Playlist     │     │  ├─ Smart search (sentence-   │
│    browser      │     │  │   transformers embeddings) │
│                 │     │  ├─ OAuth2 Google login        │
│                 │     │  └─ SQLite database            │
└─────────────────┘     └──────────────────────────────┘
```

### Flow

1. User logs in via Google OAuth2 — grants read-only access to YouTube playlists
2. Backend fetches all playlists and their videos via YouTube Data API v3, stores in SQLite
3. Video titles and descriptions are indexed with SQLite FTS5 for keyword search
4. Video metadata is embedded using `all-MiniLM-L6-v2` (local, free, 22MB) for semantic search
5. User searches — backend runs keyword and semantic search in parallel, merges and ranks results
6. User re-syncs on demand to pick up newly saved videos

## Search System

### Keyword Search (Primary)

- SQLite FTS5 full-text index on video title, description, and channel name
- Results ranked by FTS5 built-in relevance scoring
- Handles partial matches

### Semantic Search (Enhancement)

- Each video's title + description is embedded using `all-MiniLM-L6-v2` on sync
- Embeddings stored as binary blobs in SQLite
- At search time, query is embedded and compared via cosine similarity
- Catches cases where search terms don't exactly match the title (e.g., searching "CSS grid layout" finds "Building Responsive Designs with Modern CSS")

### Result Merging

- Both searches run in parallel
- Keyword matches weighted higher (more precise)
- Duplicates merged, keeping the higher score
- Results display: thumbnail, title, channel name, playlist name(s), link to open in YouTube

## Data Model

### SQLite Tables

- **users** — Google user ID, OAuth tokens (encrypted), last sync timestamp
- **playlists** — playlist ID, user ID, title, description, thumbnail URL
- **videos** — video ID, title, description, channel name, thumbnail URL, published date
- **playlist_videos** — many-to-many link (a video can appear in multiple playlists), includes position and date added
- **embeddings** — video ID, embedding vector (binary blob)

### Sync Behavior

- **Initial sync:** Fetches all playlists and all videos on first login. Generates embeddings for all videos (hundreds of videos with the small model should take under a minute).
- **Incremental sync:** On subsequent visits, detects playlist changes via ETag or item count, only fetches and embeds new/changed videos.
- **Manual re-sync:** "Sync Now" button in the UI.
- **No background polling** — sync happens on login and on-demand.

## Frontend UI

### Layout

Single-page app with three areas:

- **Top bar** — Google login/logout, user avatar, "Sync Now" button with last-synced timestamp
- **Search area** — Single search input, prominent and centered. Toggle for "All Playlists" vs filtering to a specific playlist.
- **Results area** — Card grid showing: thumbnail, title, channel name, playlist name(s), published date. Clicking a card opens the video on YouTube in a new tab.

### Playlist Browsing (Nice-to-Have)

- Sidebar or secondary view listing all playlists as browsable categories
- Click a playlist to see all its videos, with search filtering within that playlist

### Interactions

- Live search (debounced ~300ms) — results update as you type
- Loading spinner during sync
- Empty states for "no results" and "no videos synced yet"

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLite (with FTS5), sentence-transformers (`all-MiniLM-L6-v2`), Google API Python client, python-dotenv
- **Frontend:** React 18 (Vite), plain CSS
- **Auth:** Google OAuth2 (read-only YouTube scope)
- **Storage:** SQLite (single file, no external database needed)
- **Launcher:** `start.bat` for one-click startup on Windows

## Non-Goals

- Mobile app or browser extension (future expansion)
- Video playback within the app
- Social features or multi-user collaboration
- Automatic background syncing or scheduled jobs
- Paid AI API integration
