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
