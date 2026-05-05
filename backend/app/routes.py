from fastapi import APIRouter, Request, HTTPException

from app.auth import require_user
from app.config import settings
from app.database import get_connection
from app.search import keyword_search, combined_search, list_playlist_videos
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
        if playlist_id:
            raw_results = list_playlist_videos(settings.DATABASE_PATH, user_id, playlist_id)
        else:
            return {"results": [], "query": q, "total": 0}
    elif mode == "keyword":
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
        "SELECT access_token_encrypted, refresh_token_encrypted FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if not user or not user["access_token_encrypted"]:
        raise HTTPException(status_code=400, detail="No access token found. Please re-login.")

    access_token = user["access_token_encrypted"].decode()
    refresh_token_blob = user["refresh_token_encrypted"]
    refresh_token = refresh_token_blob.decode() if refresh_token_blob else None
    result = sync_user_playlists(settings.DATABASE_PATH, user_id, access_token, refresh_token)

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
