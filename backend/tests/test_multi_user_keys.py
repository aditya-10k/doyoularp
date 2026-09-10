import json
import pytest
import httpx
from backend.app.agents.groq_client import GroqClient
from backend.tests.test_api_endpoints import generate_dummy_pdf


def test_groq_client_multiple_keys():
    user_keys = [
        {"provider": "groq", "api_key": "gsk_first"},
        {"provider": "gemini", "api_key": "AIzaSy_second"},
        {"provider": "openai", "api_key": "sk_third"},
    ]
    client = GroqClient(user_keys=user_keys)
    assert len(client.user_keys) == 3
    assert client.user_keys[0]["provider"] == "groq"
    assert client.user_keys[0]["api_key"] == "gsk_first"
    assert client.user_keys[1]["provider"] == "gemini"
    assert client.user_keys[1]["api_key"] == "AIzaSy_second"
    assert client.user_keys[2]["provider"] == "openai"
    assert client.user_keys[2]["api_key"] == "sk_third"
    assert client.is_configured is True


def test_groq_client_legacy_single_key():
    client = GroqClient(user_api_key="gsk_legacy", user_provider="groq")
    assert len(client.user_keys) == 1
    assert client.user_keys[0]["provider"] == "groq"
    assert client.user_keys[0]["api_key"] == "gsk_legacy"


@pytest.mark.asyncio
async def test_upload_resume_with_multi_keys_header(client: httpx.AsyncClient):
    create_resp = await client.post("/api/v1/analyses", json={"alias": "MultiKey Tester"})
    assert create_resp.status_code == 201
    analysis_id = create_resp.json()["analysis_id"]

    pdf_bytes = generate_dummy_pdf()
    files = {"file": ("test_resume.pdf", pdf_bytes, "application/pdf")}
    keys_payload = [
        {"provider": "groq", "api_key": "gsk_user_test_1"},
        {"provider": "gemini", "api_key": "AIzaSy_user_test_2"},
    ]
    headers = {
        "X-User-Api-Keys": json.dumps(keys_payload),
    }

    upload_resp = await client.post(
        f"/api/v1/analyses/{analysis_id}/resume",
        files=files,
        headers=headers,
    )
    assert upload_resp.status_code == 200
    data = upload_resp.json()
    assert data["analysis_id"] == analysis_id
