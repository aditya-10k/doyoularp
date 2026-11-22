import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import httpx

from backend.app.agents.groq_client import GroqClient, GroqRateLimitError
from backend.app.core.config import settings


def test_is_configured_with_free_providers():
    """Verify is_configured is True when free tier providers or GITHUB_TOKEN are set."""
    with patch.object(settings, "GROQ_API_KEY", None), \
         patch.object(settings, "CEREBRAS_API_KEY", None), \
         patch.object(settings, "GITHUB_MODELS_TOKEN", None), \
         patch.object(settings, "GITHUB_TOKEN", None), \
         patch.object(settings, "SAMBANOVA_API_KEY", None), \
         patch.object(settings, "GEMINI_API_KEY", None), \
         patch.object(settings, "OPENROUTER_API_KEY", None), \
         patch.object(settings, "OPENAI_API_KEY", None), \
         patch.object(settings, "MISTRAL_API_KEY", None), \
         patch.object(settings, "ANTHROPIC_API_KEY", None):

        client_empty = GroqClient()
        assert client_empty.is_configured is False

        # 1. GITHUB_TOKEN alone activates free GitHub Models
        with patch.object(settings, "GITHUB_TOKEN", "ghp_mock_token_123"):
            client_gh = GroqClient()
            assert client_gh.is_configured is True

        # 2. Cerebras API key alone
        with patch.object(settings, "CEREBRAS_API_KEY", "csk_mock_cerebras"):
            client_cer = GroqClient()
            assert client_cer.is_configured is True

        # 3. SambaNova API key alone
        with patch.object(settings, "SAMBANOVA_API_KEY", "samba_mock_key"):
            client_samba = GroqClient()
            assert client_samba.is_configured is True


@pytest.mark.asyncio
async def test_openai_compatible_provider_adapter():
    """Verify _try_openai_compatible_provider parses response and passes headers."""
    client = GroqClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "{\"result\": \"success\"}"}}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        res = await client._try_openai_compatible_provider(
            provider_name="TestProvider",
            base_url="https://api.testprovider.com/v1",
            api_key="test_key_abc",
            models=["test-model-70b"],
            system_prompt="System prompt",
            user_prompt="User prompt",
            temperature=0.8,
            json_mode=True,
            frequency_penalty=0.5,
            presence_penalty=0.5,
        )

        assert res == '{"result": "success"}'
        mock_post.assert_awaited_once()

        call_args, call_kwargs = mock_post.call_args
        assert call_args[0] == "https://api.testprovider.com/v1/chat/completions"
        assert call_kwargs["headers"]["Authorization"] == "Bearer test_key_abc"
        assert call_kwargs["json"]["model"] == "test-model-70b"
        assert call_kwargs["json"]["temperature"] == 0.8
        assert call_kwargs["json"]["frequency_penalty"] == 0.5
        assert call_kwargs["json"]["presence_penalty"] == 0.5
        assert call_kwargs["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_openai_compatible_provider_400_json_retry():
    """Verify that if provider returns 400 on response_format, adapter retries without it."""
    client = GroqClient()

    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = "Error: response_format is not supported by this model"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "choices": [{"message": {"content": "{\"recovered\": true}"}}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_resp_400, mock_resp_200]

        res = await client._try_openai_compatible_provider(
            provider_name="StrictProvider",
            base_url="https://api.strictprovider.com/v1",
            api_key="strict_key",
            models=["strict-model"],
            system_prompt="Sys",
            user_prompt="User",
            json_mode=True,
        )

        assert res == '{"recovered": true}'
        assert mock_post.await_count == 2

        # First call attempted with response_format
        first_payload = mock_post.call_args_list[0].kwargs["json"]
        assert "response_format" in first_payload

        # Second call retried without response_format
        second_payload = mock_post.call_args_list[1].kwargs["json"]
        assert "response_format" not in second_payload


@pytest.mark.asyncio
async def test_cascade_failover_to_github_models():
    """Verify automated failover: Groq fails, Cerebras fails (429), falls through to GitHub Models."""
    client = GroqClient(api_key="fake_groq_key")

    with patch.object(settings, "CEREBRAS_API_KEY", "csk_mock"), \
         patch.object(settings, "GITHUB_TOKEN", "ghp_mock_token"), \
         patch.object(client._client.chat.completions, "create", side_effect=Exception("Groq offline")), \
         patch.object(client, "_try_cerebras", new_callable=AsyncMock, return_value=None), \
         patch.object(client, "_try_github_models", new_callable=AsyncMock) as mock_gh_models:

        mock_gh_models.return_value = '{"provider": "github_models", "status": "ok"}'

        result = await client.chat_completion(
            system_prompt="System",
            user_prompt="User",
            json_mode=True,
        )

        assert "github_models" in result
        mock_gh_models.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_supplied_keys_with_free_providers():
    """Verify user-provided Cerebras and SambaNova keys are routed to the corresponding provider."""
    # 1. User supplied Cerebras key
    client_user_cerebras = GroqClient(
        user_keys=[{"provider": "cerebras", "api_key": "user_csk_999"}]
    )
    with patch.object(client_user_cerebras, "_try_cerebras", new_callable=AsyncMock) as mock_cer:
        mock_cer.return_value = '{"answer": "cerebras_user"}'

        ans = await client_user_cerebras.chat_completion("Sys", "User")
        assert ans == '{"answer": "cerebras_user"}'
        mock_cer.assert_awaited_once()
        assert mock_cer.call_args.kwargs.get("custom_key") == "user_csk_999"

    # 2. User supplied SambaNova key
    client_user_samba = GroqClient(
        user_keys=[{"provider": "sambanova", "api_key": "user_samba_888"}]
    )
    with patch.object(client_user_samba, "_try_sambanova", new_callable=AsyncMock) as mock_samba:
        mock_samba.return_value = '{"answer": "sambanova_user"}'

        ans_samba = await client_user_samba.chat_completion("Sys", "User")
        assert ans_samba == '{"answer": "sambanova_user"}'
        mock_samba.assert_awaited_once()
        assert mock_samba.call_args.kwargs.get("custom_key") == "user_samba_888"
