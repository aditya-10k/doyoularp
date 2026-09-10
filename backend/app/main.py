import os
import sys

# Ensure repository root is in sys.path regardless of working directory
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes import analyses
from backend.app.core.config import settings
from backend.app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schemas on startup
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Resume evidence-verification and brutal roast engine.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration: Allow localhost ports, Vercel deployments, and custom FRONTEND_URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://doyoularp.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(analyses.router, prefix="/api/v1")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serves the favicon if present, or responds with 204 No Content to avoid 404 logs."""
    static_fav = os.path.join(os.path.dirname(__file__), "static", "favicon.ico")
    if os.path.exists(static_fav):
        return FileResponse(static_fav, media_type="image/x-icon")
    root_fav = os.path.join(_repo_root, "frontend", "public", "favicon.ico")
    if os.path.exists(root_fav):
        return FileResponse(root_fav, media_type="image/x-icon")
    return Response(status_code=204)


@app.get("/api/v1/leaderboard", tags=["Leaderboard"])
async def api_global_leaderboard():
    from backend.app.db.session import async_session_maker
    from backend.app.api.routes.analyses import _fetch_leaderboard_response
    async with async_session_maker() as db:
        return await _fetch_leaderboard_response(db, None)


@app.get("/health", tags=["Health"])
async def health_check():
    providers = {
        "groq": bool(settings.GROQ_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY),
        "openai": bool(settings.OPENAI_API_KEY),
        "mistral": bool(settings.MISTRAL_API_KEY),
        "anthropic": bool(settings.ANTHROPIC_API_KEY),
    }
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "groq_configured": bool(settings.GROQ_API_KEY),
        "groq_model": settings.GROQ_MODEL,
        "primary_model": settings.GROQ_MODEL,
        "providers": providers,
        "active_provider_count": sum(1 for v in providers.values() if v),
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "doyoularp API is running. Upload resumes to /api/v1/analyses for brutal sanity checks.",
        "docs": "/docs",
    }
