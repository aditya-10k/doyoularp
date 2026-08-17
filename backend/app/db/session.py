import json
import socket
import urllib.parse
import urllib.request
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.config import settings

# Resilient DNS fallback for freshly created cloud databases (e.g. Neon.tech)
_orig_getaddrinfo = socket.getaddrinfo

def _resilient_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        if isinstance(host, str) and (".neon.tech" in host or ".render.com" in host):
            try:
                doh_url = f"https://dns.google/resolve?name={host}&type=A"
                req = urllib.request.Request(doh_url, headers={"User-Agent": "doyoularp/1.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    for ans in data.get("Answer", []):
                        if ans.get("type") == 1 and "data" in ans:
                            return _orig_getaddrinfo(ans["data"], port, family, type, proto, flags)
            except Exception:
                pass
        raise

socket.getaddrinfo = _resilient_getaddrinfo


class Base(DeclarativeBase):
    pass


def normalize_database_url(raw_url: str) -> str:
    """
    Normalizes PostgreSQL connection strings (e.g. from Neon.tech, Supabase, Render)
    to use SQLAlchemy's async driver (asyncpg) and compatible SSL parameters.
    """
    if not raw_url:
        return "sqlite+aiosqlite:///./larp_checker.db"

    url = raw_url.strip()
    if url.startswith("psql "):
        url = url[len("psql "):].strip().strip("'\"")

    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    # Parse and rebuild query parameters cleanly for asyncpg
    if "?" in url:
        base, query = url.split("?", 1)
        params = urllib.parse.parse_qs(query)
        ssl_val = params.pop("sslmode", [None])[0] or params.pop("ssl", [None])[0]
        params.pop("channel_binding", None)  # asyncpg does not take channel_binding

        rebuilt = []
        if ssl_val:
            rebuilt.append(f"ssl={ssl_val}")
        for k, v_list in params.items():
            for v in v_list:
                rebuilt.append(f"{k}={v}")

        url = base + ("?" + "&".join(rebuilt) if rebuilt else "")

    return url


from sqlalchemy.pool import NullPool

# Configure async engine
normalized_db_url = normalize_database_url(settings.DATABASE_URL)
engine_kwargs = {"echo": False}
if normalized_db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Use NullPool for serverless PostgreSQL (Neon) and multi-loop safety
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(normalized_db_url, **engine_kwargs)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining async database session in routes."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database tables."""
    import backend.app.models.models  # noqa: F401 - register all tables with Base.metadata
    async with engine.begin() as conn:
        # If postgresql and pgvector are used, vector extension can be enabled
        if "postgresql" in settings.DATABASE_URL:
            try:
                from sqlalchemy import text
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass
        await conn.run_sync(Base.metadata.create_all)
