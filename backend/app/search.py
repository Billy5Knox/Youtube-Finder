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
