from unittest.mock import MagicMock, patch
from app.youtube import fetch_playlists, fetch_playlist_videos


def _mock_playlists_response():
    return {
        "items": [
            {
                "id": "PLabc123",
                "snippet": {
                    "title": "Web Dev",
                    "description": "Web development tutorials",
                    "thumbnails": {"medium": {"url": "https://example.com/thumb1.jpg"}},
                },
                "contentDetails": {"itemCount": 5},
                "etag": "etag123",
            },
            {
                "id": "PLdef456",
                "snippet": {
                    "title": "Python",
                    "description": "Python tutorials",
                    "thumbnails": {"medium": {"url": "https://example.com/thumb2.jpg"}},
                },
                "contentDetails": {"itemCount": 3},
                "etag": "etag456",
            },
        ],
        "nextPageToken": None,
    }


def _mock_playlist_items_response():
    return {
        "items": [
            {
                "snippet": {
                    "resourceId": {"videoId": "vid001"},
                    "title": "React Hooks Tutorial",
                    "description": "Learn React hooks",
                    "videoOwnerChannelTitle": "Fireship",
                    "thumbnails": {"medium": {"url": "https://example.com/vid1.jpg"}},
                    "publishedAt": "2024-01-15T00:00:00Z",
                    "position": 0,
                },
                "contentDetails": {"videoPublishedAt": "2024-01-10T00:00:00Z"},
            },
        ],
        "nextPageToken": None,
    }


@patch("app.youtube._build_youtube_service")
def test_fetch_playlists(mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    mock_service.playlists().list().execute.return_value = _mock_playlists_response()

    playlists = fetch_playlists("fake_token")

    assert len(playlists) == 2
    assert playlists[0]["id"] == "PLabc123"
    assert playlists[0]["title"] == "Web Dev"
    assert playlists[1]["id"] == "PLdef456"


@patch("app.youtube._build_youtube_service")
def test_fetch_playlist_videos(mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    mock_service.playlistItems().list().execute.return_value = _mock_playlist_items_response()

    videos = fetch_playlist_videos("fake_token", "PLabc123")

    assert len(videos) == 1
    assert videos[0]["video_id"] == "vid001"
    assert videos[0]["title"] == "React Hooks Tutorial"
    assert videos[0]["channel_name"] == "Fireship"
