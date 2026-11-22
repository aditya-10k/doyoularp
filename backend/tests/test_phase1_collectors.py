import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from backend.app.collectors.web_collector import WebCollector
from backend.app.collectors.github_collector import (
    GitHubCollector,
    _REPO_CACHE,
    TARGET_MANIFEST_NAMES,
)


@pytest.mark.asyncio
async def test_web_collector_jina_reader_integration():
    collector = WebCollector()

    # Mock Jina Reader successful response
    mock_jina_resp = MagicMock()
    mock_jina_resp.status_code = 200
    mock_jina_resp.text = "Title: Awesome Developer Portfolio\n\nFull stack developer specialized in Next.js and React."

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_jina_resp
        res = await collector.fetch_page("https://johndoe.dev")
        assert res["status"] == "collected"
        assert res["engine"] == "jina_reader"
        assert "Awesome Developer Portfolio" in res["title"]
        assert "Full stack developer" in res["content"]


@pytest.mark.asyncio
async def test_web_collector_jina_fallback_to_beautifulsoup():
    collector = WebCollector()

    # Mock Jina Reader failing, but direct HTTP GET returning valid HTML
    async def mock_get(url, *args, **kwargs):
        resp = MagicMock()
        if "r.jina.ai" in url:
            resp.status_code = 500
            resp.text = ""
        else:
            resp.status_code = 200
            resp.headers = {"content-type": "text/html"}
            resp.text = "<html><head><title>Fallback Portfolio</title></head><body><h1>Welcome</h1><p>Building scalable systems.</p></body></html>"
        return resp

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
        res = await collector.fetch_page("https://johndoe.dev")
        assert res["status"] == "collected"
        assert res.get("engine") != "jina_reader"
        assert "Fallback Portfolio" in res["title"]
        assert "Building scalable systems" in res["content"]


@pytest.mark.asyncio
async def test_github_token_rotation():
    with patch("backend.app.collectors.github_collector.settings") as mock_settings:
        mock_settings.GITHUB_TOKENS = "token_alpha, token_beta, token_gamma"
        mock_settings.GITHUB_TOKEN = "single_token"
        mock_settings.MAX_CONCURRENT_GITHUB_REQS = 5

        collector = GitHubCollector()
        assert len(collector.tokens) == 3

        # Successive headers should cycle through the tokens in round-robin
        tok1 = collector._api_headers()["Authorization"]
        tok2 = collector._api_headers()["Authorization"]
        tok3 = collector._api_headers()["Authorization"]
        tok4 = collector._api_headers()["Authorization"]

        assert tok1 == "Bearer token_alpha"
        assert tok2 == "Bearer token_beta"
        assert tok3 == "Bearer token_gamma"
        assert tok4 == "Bearer token_alpha"


@pytest.mark.asyncio
async def test_github_trees_manifest_discovery():
    collector = GitHubCollector(token="test_tok")

    mock_tree_data = {
        "tree": [
            {"path": "packages/backend/pom.xml", "type": "blob"},
            {"path": "packages/frontend/package.json", "type": "blob"},
            {"path": "deploy/Dockerfile", "type": "blob"},
            {"path": "deep/folder/notes.txt", "type": "blob"},
        ]
    }

    async def mock_api_get(client, endpoint, params=None):
        if "git/trees" in endpoint:
            return mock_tree_data
        return None

    collector._api_get = AsyncMock(side_effect=mock_api_get)

    async def mock_raw_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "pom.xml" in url:
            resp.text = "<project><artifactId>core-api</artifactId></project>"
        elif "package.json" in url:
            resp.text = '{"name": "web-client", "dependencies": {"next": "14.0.0"}}'
        elif "Dockerfile" in url:
            resp.text = "FROM node:20-alpine\nEXPOSE 3000"
        elif "README" in url:
            resp.text = "# Monorepo Project"
        else:
            resp.status_code = 404
            resp.text = ""
        return resp

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", side_effect=mock_raw_get):
            readme, manifests = await collector.harvest_repo_manifests_and_readme(
                client, "acme-corp", "monorepo"
            )

            assert readme is not None
            assert "packages/backend/pom.xml" in manifests
            assert "packages/frontend/package.json" in manifests
            assert "deploy/Dockerfile" in manifests
            assert "deep/folder/notes.txt" not in manifests


@pytest.mark.asyncio
async def test_repo_cache_prevents_duplicate_fetches():
    collector = GitHubCollector(token="test_tok")
    _REPO_CACHE.clear()

    mock_repo_payload = {
        "description": "High performance cache",
        "stargazers_count": 42,
        "forks_count": 5,
        "pushed_at": "2026-11-01T12:00:00Z",
        "default_branch": "main",
    }

    collector._api_get = AsyncMock(return_value=mock_repo_payload)
    collector.harvest_repo_manifests_and_readme = AsyncMock(
        return_value=("# Readme", {"package.json": {"content": "{}", "meta": {}}})
    )

    # First fetch: should compute and cache
    res1 = await collector.collect_single_repo("testowner", "fastcache", candidate_username="testowner")
    assert res1 is not None
    assert "testowner/fastcache:2026-11-01T12:00:00Z" in _REPO_CACHE

    # Second fetch: harvest_repo_manifests_and_readme should NOT be called again
    collector.harvest_repo_manifests_and_readme.reset_mock()
    res2 = await collector.collect_single_repo("testowner", "fastcache", candidate_username="testowner")
    assert res2 is not None
    assert collector.harvest_repo_manifests_and_readme.call_count == 0


@pytest.mark.asyncio
async def test_autonomous_project_search():
    collector = GitHubCollector(token="test_tok")

    mock_search_res = {
        "items": [
            {
                "name": "super-kv-store",
                "owner": {"login": "alice_dev"},
            }
        ]
    }

    collector._api_get = AsyncMock(return_value=mock_search_res)
    collector.collect_single_repo = AsyncMock(
        return_value={"name": "super-kv-store", "owner": "alice_dev", "stars": 120}
    )

    found = await collector.search_user_project("alice_dev", "super-kv-store")
    assert found is not None
    assert found["name"] == "super-kv-store"
    assert found["owner"] == "alice_dev"
