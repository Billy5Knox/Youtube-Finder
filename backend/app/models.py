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
