import json
import pytest
from unittest.mock import AsyncMock, patch

from backend.app.agents.roast_agent import (
    ROAST_ARCHETYPES,
    RoastAgent,
    build_roast_system_prompt,
)
from backend.app.agents.groq_client import GroqClient


def test_roast_archetypes_structure():
    """Verify all 5 distinct archetypes exist with necessary configuration."""
    expected_keys = [
        "exhausted_principal",
        "gordon_ramsay",
        "cynical_vc",
        "oss_purist",
        "hn_skeptic",
    ]
    for key in expected_keys:
        assert key in ROAST_ARCHETYPES, f"Missing archetype: {key}"
        arch = ROAST_ARCHETYPES[key]
        assert "title" in arch and len(arch["title"]) > 5
        assert "tagline" in arch and len(arch["tagline"]) > 5
        assert "persona_prompt" in arch and len(arch["persona_prompt"]) > 20


def test_build_roast_system_prompt():
    """Verify system prompt generation embodies the selected archetype."""
    prompt, key = build_roast_system_prompt("gordon_ramsay")
    assert key == "gordon_ramsay"
    assert "Gordon Ramsay" in prompt
    assert "Raw!" in prompt
    # Ensure old canned TikTok mandate was removed from prompt
    assert "Go and make TikToks, pray you get diversity hired" not in prompt

    # Random selection works without error
    prompt_rand, key_rand = build_roast_system_prompt(None)
    assert key_rand in ROAST_ARCHETYPES
    assert ROAST_ARCHETYPES[key_rand]["title"] in prompt_rand


def test_fallback_roast_dynamism_no_github():
    """Verify procedural fallback produces varied combinations when has_github=False."""
    agent = RoastAgent()
    evals = [
        {"claim_text": "Built enterprise cloud architecture", "verdict": "UNVERIFIED"},
    ]

    outputs = set()
    verdicts = set()
    mismatches = set()

    for _ in range(20):
        roast = agent._fallback_roast(larp_score=100.0, evaluations=evals, repos=[], has_github=False)
        assert "overall_roast" in roast
        assert "verdict_summary" in roast
        assert "funny_mismatch" in roast
        assert roast["strongest_claim"] == "None"
        assert len(roast["overall_roast"]) > 50

        outputs.add(roast["overall_roast"])
        verdicts.add(roast["verdict_summary"])
        mismatches.add(roast["funny_mismatch"])

    # In 20 iterations across 5x5x5 banks, we must observe variety
    assert len(outputs) > 1, "Procedural fallback produced identical roasts on multiple runs"
    assert len(verdicts) > 1, "Procedural fallback produced identical verdicts on multiple runs"
    assert len(mismatches) > 1, "Procedural fallback produced identical mismatches on multiple runs"


def test_fallback_roast_dynamism_high_larp():
    """Verify procedural fallback produces varied combinations for high LARP scores."""
    agent = RoastAgent()
    evals = [
        {"claim_text": "Engineered 100,000 QPS Kafka broker", "verdict": "CONTRADICTED"},
    ]
    repos = [{"name": "kafka-starter"}]

    outputs = set()
    for _ in range(20):
        roast = agent._fallback_roast(larp_score=85.0, evaluations=evals, repos=repos, has_github=True)
        assert "overall_roast" in roast
        assert "100,000 QPS Kafka broker" in roast["weakest_claim"]
        outputs.add(roast["overall_roast"])

    assert len(outputs) > 1, "Procedural fallback produced identical high-LARP roasts"


@pytest.mark.asyncio
async def test_generate_roast_llm_hyperparameters_and_fuel():
    """Verify LLM is supplied with rich ammunition and anti-repetition hyperparameters."""
    mock_groq = AsyncMock(spec=GroqClient)
    mock_groq.is_configured = True
    mock_groq.chat_completion = AsyncMock(
        return_value=json.dumps({
            "overall_roast": "A devastatingly unique and dynamic roast tailored to the candidate.",
            "verdict_summary": "Devastating reality disconnect.",
            "strongest_claim": "None",
            "weakest_claim": "Engineered 50,000 QPS distributed engine",
            "funny_mismatch": "Claimed distributed scale, delivered a single toy script.",
        })
    )
    mock_groq.extract_json = lambda text: json.loads(text)

    agent = RoastAgent(groq_client=mock_groq)

    evals = [
        {
            "claim_text": "Engineered 50,000 QPS distributed engine",
            "source_text": "Engineered custom distributed broker handling 50,000 QPS in production",
            "verdict": "CONTRADICTED",
            "reasoning": "Repository has 2 commits and 0 performance tests.",
        },
        {
            "claim_text": "Built frontend in React",
            "source_text": "Frontend in React",
            "verdict": "SUPPORTED",
            "reasoning": "React package verified.",
        },
    ]
    repos = [
        {
            "name": "distributed-engine",
            "candidate_commit_count": 2,
            "total_commit_count": 2,
            "languages": {"Python": 1500},
        }
    ]

    result = await agent.generate_roast(
        larp_score=82.0,
        evaluations=evals,
        repos=repos,
        intensity=3,
        has_github=True,
        candidate_alias="AsyncAlchemist",
        competitive_stats={"leetcode": {"solved": 15, "contest_rating": 1400}},
        suspicious_dependencies=["is-odd", "create-react-app"],
        archetype="cynical_vc",
    )

    assert result["roast_archetype"] == "cynical_vc"
    assert "devastatingly unique" in result["overall_roast"]

    # Verify Groq was called with correct anti-repetition hyperparams
    mock_groq.chat_completion.assert_awaited_once()
    call_kwargs = mock_groq.chat_completion.call_args.kwargs

    assert call_kwargs.get("temperature") == 0.95
    assert call_kwargs.get("frequency_penalty") == 0.6
    assert call_kwargs.get("presence_penalty") == 0.5
    assert call_kwargs.get("json_mode") is True

    # Verify prompt payload contained rich granular fuel
    payload_str = call_kwargs.get("user_prompt")
    payload = json.loads(payload_str)

    assert payload["candidate_alias"] == "AsyncAlchemist"
    assert payload["worst_contradiction"]["claim"] == "Engineered 50,000 QPS distributed engine"
    assert "50,000 QPS" in payload["worst_contradiction"]["source_quote"]
    assert "is-odd" in payload["suspicious_dependencies"]
    assert payload["competitive_programming_stats"]["leetcode"]["solved"] == 15
    assert "Cynical VC" in payload["roast_archetype"]


@pytest.mark.asyncio
async def test_no_github_llm_roast_no_hardcoded_overwrite():
    """Verify that when has_github=False, LLM output is preserved and not overwritten with static TikTok text."""
    mock_groq = AsyncMock(spec=GroqClient)
    mock_groq.is_configured = True
    custom_llm_roast = "You submitted a ghost resume with zero code provenance. A true architectural phantom."
    custom_verdict = "Ghost candidate detected."
    custom_mismatch = "Claimed microservices; provided a blank URL."

    mock_groq.chat_completion = AsyncMock(
        return_value=json.dumps({
            "overall_roast": custom_llm_roast,
            "verdict_summary": custom_verdict,
            "strongest_claim": "None",
            "weakest_claim": "Zero GitHub profile or repository links provided",
            "funny_mismatch": custom_mismatch,
        })
    )
    mock_groq.extract_json = lambda text: json.loads(text)

    agent = RoastAgent(groq_client=mock_groq)

    result = await agent.generate_roast(
        larp_score=100.0,
        evaluations=[],
        repos=[],
        intensity=3,
        has_github=False,
    )

    # Must contain LLM's dynamic roast and NOT have the static TikTok lead line prepended
    assert result["overall_roast"] == custom_llm_roast
    assert "Go and make TikToks, pray you get diversity hired" not in result["overall_roast"]
    assert result["verdict_summary"] == custom_verdict
    assert result["funny_mismatch"] == custom_mismatch
