import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from backend.app.collectors.competitive_collector import CompetitiveCollector
from backend.app.collectors.linkedin_collector import LinkedInCollector
from backend.app.parsers.url_extractor import (
    classify_url,
    parse_leetcode_url,
    parse_codeforces_url,
    parse_linkedin_url,
    extract_profile_handles_from_text,
)
from backend.app.agents.evaluation_agent import check_competitive_programming_claim
from backend.app.rag.evidence_retriever import RetrievedEvidenceChunk


def test_competitive_url_parsing():
    # LeetCode
    assert classify_url("https://leetcode.com/u/alice_coder/") == "leetcode"
    lc = parse_leetcode_url("https://leetcode.com/u/alice_coder")
    assert lc is not None
    assert lc["username"] == "alice_coder"

    # Reserved leetcode path
    assert parse_leetcode_url("https://leetcode.com/problems/two-sum") is None

    # Codeforces
    assert classify_url("https://codeforces.com/profile/tourist") == "codeforces"
    cf = parse_codeforces_url("https://codeforces.com/profile/tourist")
    assert cf is not None
    assert cf["handle"] == "tourist"

    # LinkedIn
    assert classify_url("https://www.linkedin.com/in/john-doe-123/") == "linkedin"
    li = parse_linkedin_url("https://www.linkedin.com/in/john-doe-123/")
    assert li is not None
    assert li["handle"] == "john-doe-123"


def test_plain_text_handle_extraction():
    text = """
    John Doe | Full Stack Engineer
    LeetCode: @algo_wizard
    Codeforces: competitive_beast
    Email: john@example.com
    """
    handles = extract_profile_handles_from_text(text)
    assert len(handles) == 2

    lc_handle = next((h for h in handles if h["category"] == "leetcode"), None)
    assert lc_handle is not None
    assert lc_handle["leetcode_info"]["username"] == "algo_wizard"

    cf_handle = next((h for h in handles if h["category"] == "codeforces"), None)
    assert cf_handle is not None
    assert cf_handle["codeforces_info"]["handle"] == "competitive_beast"


@pytest.mark.asyncio
async def test_codeforces_collector_success():
    collector = CompetitiveCollector()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "OK",
        "result": [
            {
                "handle": "code_wizard",
                "rating": 1750,
                "maxRating": 1920,
                "rank": "expert",
                "maxRank": "candidate master",
                "contribution": 15,
            }
        ],
    }

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await collector.fetch_codeforces_evidence("code_wizard")
        assert res["status"] == "collected"
        assert res["rank"] == "expert"
        assert res["peak_rating"] == 1920
        assert "Candidate Master" in res["summary"]


@pytest.mark.asyncio
async def test_leetcode_collector_success():
    collector = CompetitiveCollector()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "matchedUser": {
                "username": "dsa_master",
                "submitStatsGlobal": {
                    "acSubmissionNum": [
                        {"difficulty": "All", "count": 650},
                        {"difficulty": "Easy", "count": 200},
                        {"difficulty": "Medium", "count": 350},
                        {"difficulty": "Hard", "count": 100},
                    ]
                },
                "profile": {"ranking": 12050},
            },
            "userContestRanking": {
                "rating": 1950.5,
                "topPercentage": 2.4,
                "badge": {"name": "Knight"},
            },
        }
    }

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await collector.fetch_leetcode_evidence("dsa_master")
        assert res["status"] == "collected"
        assert res["total_solved"] == 650
        assert res["hard_solved"] == 100
        assert res["badge"] == "Knight"
        assert "Knight" in res["summary"]


@pytest.mark.asyncio
async def test_linkedin_collector_serper_fallback():
    collector = LinkedInCollector(serper_key="test_serper_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "organic": [
            {
                "title": "Jane Smith - Senior Backend Engineer - Stripe | LinkedIn",
                "snippet": "Experienced distributed systems engineer at Stripe building high scale payment APIs.",
                "link": "https://www.linkedin.com/in/janesmith",
            }
        ]
    }

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await collector.verify_linkedin_profile("janesmith", candidate_name="Jane Smith")
        assert res["status"] == "collected"
        assert "Senior Backend Engineer" in res["title"]
        assert "Stripe" in res["title"]


def test_deterministic_competitive_evaluation():
    # 1. LeetCode contradiction check
    lc_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_lc",
        score=0.9,
        title="LeetCode Profile (testuser)",
        content="Verified LeetCode Profile: Total Problems Solved: 40",
        url="https://leetcode.com/testuser",
        evidence_type="leetcode_profile",
        meta={"total_solved": 40},
    )

    claim_inflated = "Solved 600+ LeetCode problems with deep mastery of algorithms"
    contradiction = check_competitive_programming_claim(claim_inflated, [lc_chunk])
    assert contradiction is not None
    assert contradiction["verdict"] == "CONTRADICTED"
    assert "claimed 600+ problems solved, but verified public profile shows only 40" in contradiction["reasoning"]

    # 2. Codeforces contradiction check
    cf_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_cf",
        score=0.9,
        title="Codeforces Profile (newbie_coder)",
        content="Current Rank: Newbie (1120 rating)",
        url="https://codeforces.com/profile/newbie_coder",
        evidence_type="codeforces_profile",
        meta={"peak_rating": 1120, "max_rank": "newbie"},
    )

    claim_grandmaster = "Competitive programmer with Codeforces Grandmaster title"
    cf_contra = check_competitive_programming_claim(claim_grandmaster, [cf_chunk])
    assert cf_contra is not None
    assert cf_contra["verdict"] == "CONTRADICTED"
    assert "claimed Grandmaster, but verified public profile has a peak rating of only 1120" in cf_contra["reasoning"]
