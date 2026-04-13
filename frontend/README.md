# YouTube Finder — Frontend

React SPA built with Vite. Communicates with the FastAPI backend via proxied API calls.

## Development

```bash
npm install
npm run dev     # Dev server on :5173, proxies /api and /auth to :8000
npm run build   # Production build to dist/
```

## Structure

- `src/App.jsx` — Root component, auth state, layout
- `src/api.js` — API client (search, playlists, sync, auth)
- `src/components/TopBar.jsx` — Header with sync button, user info, logout
- `src/components/SearchBar.jsx` — Search input with debounced API calls
- `src/components/VideoCard.jsx` — Single video result card (links to YouTube)
- `src/components/ResultsGrid.jsx` — Responsive grid of VideoCards
- `src/components/PlaylistFilter.jsx` — Playlist filter chips
- `src/hooks/useSearch.js` — Debounced search hook (300ms)
