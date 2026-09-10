import pytest
import pytest_asyncio
import httpx
from backend.app.main import app
from backend.app.db.session import init_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture(scope="session", autouse=True)
def disable_live_ai_for_tests():
    from backend.app.core.config import settings
    keys = [
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "MISTRAL_API_KEY",
        "ANTHROPIC_API_KEY",
    ]
    original = {k: getattr(settings, k) for k in keys}
    for k in keys:
        setattr(settings, k, "")
    yield
    for k, v in original.items():
        setattr(settings, k, v)


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    import backend.app.agents.groq_client as groq_mod
    groq_mod._RATE_LIMITED_UNTIL = 0.0
    yield
    groq_mod._RATE_LIMITED_UNTIL = 0.0


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
