from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.auth import router as auth_router
from app.routes import router as api_router
from app.database import init_db

app = FastAPI(title="YouTube Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(api_router)


@app.on_event("startup")
def startup():
    init_db(settings.DATABASE_PATH)


@app.get("/health")
def health_check():
    return {"status": "ok"}
