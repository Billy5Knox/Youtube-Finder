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
