from contextlib import asynccontextmanager
from fastapi import FastAPI
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(analyses.router, prefix="/api/v1")


@app.get("/api/v1/leaderboard", tags=["Leaderboard"])
async def api_global_leaderboard():
    from backend.app.db.session import async_session_maker
    from backend.app.api.routes.analyses import _fetch_leaderboard_response
    async with async_session_maker() as db:
        return await _fetch_leaderboard_response(db, None)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "groq_configured": bool(settings.GROQ_API_KEY),
        "groq_model": settings.GROQ_MODEL,
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "doyoularp API is running. Upload resumes to /api/v1/analyses for brutal sanity checks.",
        "docs": "/docs",
    }
