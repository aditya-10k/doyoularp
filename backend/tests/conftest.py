import pytest
import pytest_asyncio
import httpx
from backend.app.main import app
from backend.app.db.session import init_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture(scope="session", autouse=True)
def disable_live_groq_for_tests():
    from backend.app.core.config import settings
    original_key = settings.GROQ_API_KEY
    settings.GROQ_API_KEY = ""
    yield
    settings.GROQ_API_KEY = original_key


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
