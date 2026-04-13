from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


client = TestClient(app)


def test_login_redirects_to_google():
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]


def test_me_returns_401_when_not_logged_in():
    response = client.get("/auth/me")
    assert response.status_code == 401
