import pytest
import httpx
from backend.app.utils.sanitizer import sanitize_null_bytes
from backend.app.db.session import async_session_maker
from backend.app.models.models import Evidence, Analysis, Candidate
from backend.tests.test_api_endpoints import generate_dummy_pdf_with_github


def test_sanitize_null_bytes_basic():
    # String with null bytes
    raw = "hello\x00world\x00\r\n"
    assert sanitize_null_bytes(raw) == "helloworld\r\n"

    # Nested dictionary with null bytes in keys and values
    nested_dict = {
        "repo\x00": "proto\x00",
        "nested": ["data\x001", "data\x002"],
        "count": 42,
    }
    cleaned = sanitize_null_bytes(nested_dict)
    assert cleaned == {
        "repo": "proto",
        "nested": ["data1", "data2"],
        "count": 42,
    }

    # None, int, bool pass through safely
    assert sanitize_null_bytes(None) is None
    assert sanitize_null_bytes(100) == 100
    assert sanitize_null_bytes(True) is True


@pytest.mark.asyncio
async def test_evidence_with_null_bytes_persistence():
    async with async_session_maker() as db:
        candidate = Candidate(anonymous_alias="Sanitizer Candidate")
        db.add(candidate)
        await db.flush()

        analysis = Analysis(
            candidate_id=candidate.id,
            status="running",
            stage="testing",
            progress=50,
        )
        db.add(analysis)
        await db.flush()

        raw_bad_readme = "#\x00 \x00p\x00r\x00o\x00t\x00o\x00\r\x00\n\x00Test readme with null bytes."
        clean_content = sanitize_null_bytes(raw_bad_readme)

        ev = Evidence(
            analysis_id=analysis.id,
            candidate_id=candidate.id,
            evidence_type="readme",
            title=sanitize_null_bytes("proto\x00 README"),
            content=clean_content,
            url="https://github.com/gh0gale/proto",
            meta=sanitize_null_bytes({"repo": "proto\x00"}),
        )
        db.add(ev)
        await db.commit()
        await db.refresh(ev)

        assert "\x00" not in ev.content
        assert "\x00" not in ev.title
        assert ev.meta["repo"] == "proto"


@pytest.mark.asyncio
async def test_user_api_key_headers(client: httpx.AsyncClient):
    create_resp = await client.post("/api/v1/analyses")
    assert create_resp.status_code == 201
    analysis_id = create_resp.json()["analysis_id"]

    pdf_bytes = generate_dummy_pdf_with_github()
    files = {"file": ("test_resume.pdf", pdf_bytes, "application/pdf")}
    headers = {
        "X-User-Api-Key": "gsk_test_mock_user_key",
        "X-User-Provider": "groq",
    }

    from unittest.mock import patch, AsyncMock
    with patch("backend.app.api.routes.analyses._run_pipeline_background", new_callable=AsyncMock) as mock_bg:
        upload_resp = await client.post(
            f"/api/v1/analyses/{analysis_id}/resume",
            files=files,
            headers=headers,
        )
        assert upload_resp.status_code == 200
        mock_bg.assert_called_once()
        _, kwargs = mock_bg.call_args
        assert kwargs["user_api_key"] == "gsk_test_mock_user_key"
        assert kwargs["user_provider"] == "groq"
