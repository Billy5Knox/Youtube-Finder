import json
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import get_connection, init_db
from app.shutdown import request_supervisor_shutdown

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory session store (simple approach for single-user app)
_sessions: dict[str, str] = {}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
YOUTUBE_SCOPES = "openid email profile https://www.googleapis.com/auth/youtube.readonly"


def get_current_user_id(request: Request) -> str | None:
    session_id = request.cookies.get("session_id")
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    return None


def require_user(request: Request) -> str:
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/login")
def login():
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/callback")
async def callback(code: str, request: Request):
    import httpx

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        tokens = token_response.json()

        # Get user info
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo = userinfo_response.json()

    # Store user in database
    init_db(settings.DATABASE_PATH)
    conn = get_connection(settings.DATABASE_PATH)
    conn.execute(
        """INSERT INTO users (id, email, name, picture, access_token_encrypted, refresh_token_encrypted)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             email=excluded.email,
             name=excluded.name,
             picture=excluded.picture,
             access_token_encrypted=excluded.access_token_encrypted,
             refresh_token_encrypted=excluded.refresh_token_encrypted""",
        (
            userinfo["id"],
            userinfo.get("email", ""),
            userinfo.get("name", ""),
            userinfo.get("picture", ""),
            tokens["access_token"].encode(),  # TODO: encrypt in production
            tokens.get("refresh_token", "").encode(),
        ),
    )
    conn.commit()
    conn.close()

    # Create session
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = userinfo["id"]

    response = RedirectResponse(url=settings.FRONTEND_URL)
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


@router.get("/me")
def me(request: Request):
    user_id = require_user(request)
    conn = get_connection(settings.DATABASE_PATH)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "picture": row["picture"],
        "last_sync_at": row["last_sync_at"],
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    response = RedirectResponse(url=settings.FRONTEND_URL)
    response.delete_cookie("session_id")
    return response


@router.post("/shutdown")
def shutdown(request: Request, response: Response):
    user_id = require_user(request)
    session_id = request.cookies.get("session_id")
    if session_id:
        _sessions.pop(session_id, None)
    response.delete_cookie("session_id")
    request_supervisor_shutdown()
    return {"status": "shutting_down"}
