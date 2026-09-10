import io
import pytest
import httpx
from pypdf import PdfWriter
from backend.app.db.session import async_session_maker
from backend.app.services.pipeline_service import PipelineService


def generate_dummy_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def generate_dummy_pdf_with_github() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_uri(
        page_number=0,
        uri="https://github.com/testuser/testproject",
        rect=(100, 100, 200, 120),
    )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "groq_model" in data


@pytest.mark.asyncio
async def test_create_and_query_analysis(client: httpx.AsyncClient):
    # Create analysis
    resp = await client.post("/api/v1/analyses", json={"alias": "Custom Tester #007"})
    assert resp.status_code == 201
    data = resp.json()
    assert "analysis_id" in data
    assert data["candidate_alias"] == "Custom Tester #007"
    assert data["status"] == "created"
    assert data["progress"] == 0

    analysis_id = data["analysis_id"]

    # Query analysis
    resp_get = await client.get(f"/api/v1/analyses/{analysis_id}")
    assert resp_get.status_code == 200
    get_data = resp_get.json()
    assert get_data["analysis_id"] == analysis_id
    assert get_data["candidate_alias"] == "Custom Tester #007"


@pytest.mark.asyncio
async def test_upload_resume_and_pipeline_execution(client: httpx.AsyncClient):
    # 1. Create analysis
    create_resp = await client.post("/api/v1/analyses")
    assert create_resp.status_code == 201
    analysis_id = create_resp.json()["analysis_id"]

    # 2. Upload dummy PDF
    pdf_bytes = generate_dummy_pdf()
    files = {"file": ("test_resume.pdf", pdf_bytes, "application/pdf")}
    upload_resp = await client.post(f"/api/v1/analyses/{analysis_id}/resume", files=files)
    assert upload_resp.status_code == 200
    assert upload_resp.json()["analysis_id"] == analysis_id

    # 3. Run pipeline synchronously in test
    pipeline_service = PipelineService()
    async with async_session_maker() as db:
        await pipeline_service.run_pipeline(analysis_id, "test_resume.pdf", pdf_bytes, db)

    # 4. Check status completed
    status_resp = await client.get(f"/api/v1/analyses/{analysis_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"
    assert status_resp.json()["progress"] == 100

    # 5. Check result endpoint
    result_resp = await client.get(f"/api/v1/analyses/{analysis_id}/result")
    assert result_resp.status_code == 200
    res_data = result_resp.json()
    assert "larp_score" in res_data
    assert "roast" in res_data
    assert "leaderboard_token" in res_data

    # 6. Check leaderboard endpoint
    lb_resp = await client.get(f"/api/v1/analyses/{analysis_id}/leaderboard")
    assert lb_resp.status_code == 200
    lb_data = lb_resp.json()
    assert lb_data["total"] >= 1
    assert lb_data["user_entry"] is not None
    assert lb_data["user_entry"]["anonymous_alias"] == res_data["anonymous_alias"]


@pytest.mark.asyncio
async def test_pipeline_rate_limit_failure(client: httpx.AsyncClient):
    from unittest.mock import AsyncMock
    from backend.app.agents.groq_client import GroqRateLimitError

    # 1. Create analysis
    create_resp = await client.post("/api/v1/analyses")
    assert create_resp.status_code == 201
    analysis_id = create_resp.json()["analysis_id"]

    # 2. Upload dummy PDF with GitHub link while patching background task
    from unittest.mock import patch
    pdf_bytes = generate_dummy_pdf_with_github()
    files = {"file": ("test_resume.pdf", pdf_bytes, "application/pdf")}
    with patch("backend.app.api.routes.analyses._run_pipeline_background", new_callable=AsyncMock):
        upload_resp = await client.post(f"/api/v1/analyses/{analysis_id}/resume", files=files)
        assert upload_resp.status_code == 200

    # 3. Mock evaluation_agent to raise GroqRateLimitError
    pipeline_service = PipelineService()
    pipeline_service.evaluation_agent.evaluate_claims_batch = AsyncMock(
        side_effect=GroqRateLimitError("Rate limit exceeded 429")
    )

    async with async_session_maker() as db:
        await pipeline_service.run_pipeline(analysis_id, "test_resume.pdf", pdf_bytes, db)

    # 4. Assert that analysis status is explicitly failed with rate limit error message
    status_resp = await client.get(f"/api/v1/analyses/{analysis_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "failed"
    assert status_data["stage"] == "failed"
    assert "LLM provider rate limit reached (Groq 429)" in status_data["error"]

