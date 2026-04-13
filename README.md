# YouTube Finder

Search across all your saved YouTube playlists from a single search box. Combines keyword search (SQLite FTS5) with AI-powered semantic search (sentence-transformers) to find videos even when you don't remember the exact title.

## Features

- **Unified search** — Search across all your YouTube playlists at once
- **Keyword search** — Full-text search on video titles, descriptions, and channel names
- **Semantic search** — AI-powered search that understands meaning, not just keywords (e.g., "CSS grid layout" finds "Building Responsive Designs with Modern CSS")
- **Playlist filtering** — Filter results to a specific playlist
- **Live search** — Results update as you type (300ms debounce)
- **One-click playback** — Click any result to open the video on YouTube

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google Cloud project with YouTube Data API v3 enabled and OAuth2 credentials ([setup guide](#google-oauth2-setup))

### 1. Install dependencies

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

### 2. Configure credentials

Create `backend/.env`:

```
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
SECRET_KEY=any-random-string
```

### 3. Run the app

**Option A — One-click (Windows):**

Double-click `start.bat` — starts both servers and opens your browser.

**Option B — Manual:**

```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

Then open http://localhost:5173.

### 4. Sign in and sync

1. Click "Sign in with Google"
2. Authorize YouTube read-only access
3. Click "Sync Now" to pull in your playlists
4. Start searching!

## Google OAuth2 Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **YouTube Data API v3** (APIs & Services > Library)
4. Configure **OAuth consent screen** (External, add your email as test user)
5. Add scopes: `youtube.readonly`, `openid`, `email`, `profile`
6. Create **OAuth client ID** (Web application)
7. Add authorized redirect URI: `http://localhost:8000/auth/callback`
8. Copy the Client ID and Client Secret to `backend/.env`

## Tech Stack

- **Backend:** Python, FastAPI, SQLite (FTS5), sentence-transformers (`all-MiniLM-L6-v2`), python-dotenv
- **Frontend:** React 18, Vite
- **Auth:** Google OAuth2
- **Search:** SQLite FTS5 (keyword) + cosine similarity on sentence embeddings (semantic)
